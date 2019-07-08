import copy
import logging

import gym
import numpy as np
from gym import spaces
from gym.utils import seeding

from ..utils.action_space import MultiAgentActionSpace
from ..utils.draw import draw_grid, fill_cell, draw_circle

logger = logging.getLogger(__name__)


class Checkers(gym.Env):
    """
    The map contains apples and lemons. The first player (red) is very sensitive and scores 5 for
    the team for an apple (green square) and −5 for a lemon (orange square). The second (blue), less sensitive
    player scores 1 for the team for an apple and −1 for a lemon. There is a wall of lemons between the
    players and the apples. Apples and lemons disappear when collected, and the environment resets
    when all apples are eaten. It is important that the sensitive agent eats the apples while the less sensitive
    agent should leave them to its team mate but clear the way by eating obstructing lemons.

    Reference Paper : Value-Decomposition Networks For Cooperative Multi-Agent Learning ( Section 4.2)
    """
    metadata = {'render.modes': ['human', 'rgb_array']}

    def __init__(self, full_observable=False, step_cost=0):
        self._grid_shape = (3, 8)
        self.n_agents = 2
        self._max_steps = 100
        self._step_count = None
        self._step_cost = step_cost

        self.action_space = MultiAgentActionSpace([spaces.Discrete(5) for _ in range(self.n_agents)])
        self.init_agent_pos = {0: [0, self._grid_shape[1] - 2], 1: [2, self._grid_shape[1] - 2]}
        self.agent_reward = {0: {'lemon': -5, 'apple': 5},
                             1: {'lemon': -1, 'apple': 1}}
        self.agent_prev_pos = None

        self._base_grid = None  # with no agents
        self._full_obs = None
        self._agent_dones = None
        self.viewer = None
        self.full_observable = full_observable

        self.__total_episode_reward = None

    def __draw_base_img(self):
        self._base_img = draw_grid(self._grid_shape[0], self._grid_shape[1], cell_size=CELL_SIZE, fill='white')
        for row in range(self._grid_shape[0]):
            for col in range(self._grid_shape[1]):
                if PRE_IDS['wall'] in self._full_obs[row][col]:
                    fill_cell(self._base_img, (row, col), cell_size=CELL_SIZE, fill=WALL_COLOR, margin=0.05)
                elif PRE_IDS['lemon'] in self._full_obs[row][col]:
                    fill_cell(self._base_img, (row, col), cell_size=CELL_SIZE, fill=LEMON_COLOR, margin=0.05)
                elif PRE_IDS['apple'] in self._full_obs[row][col]:
                    fill_cell(self._base_img, (row, col), cell_size=CELL_SIZE, fill=APPLE_COLOR, margin=0.05)

    def __create_grid(self):
        _grid = []
        for row in range(self._grid_shape[0]):
            if row % 2 == 0:
                _grid.append([PRE_IDS['apple'] if (c % 2 == 0) else PRE_IDS['lemon']
                              for c in range(self._grid_shape[1] - 2)] + [PRE_IDS['empty'], PRE_IDS['empty']])
            else:
                _grid.append([PRE_IDS['apple'] if (c % 2 != 0) else PRE_IDS['lemon']
                              for c in range(self._grid_shape[1] - 2)] + [PRE_IDS['empty'], PRE_IDS['empty']])

        return _grid

    def __init_full_obs(self):
        self.agent_pos = copy.copy(self.init_agent_pos)
        self.agent_prev_pos = copy.copy(self.init_agent_pos)
        self._full_obs = self.__create_grid()
        for agent_i in range(self.n_agents):
            self.__update_agent_view(agent_i)
        self.__draw_base_img()

    def get_agent_obs(self):
        _obs = []
        for agent_i in range(self.n_agents):
            pos = self.agent_pos[agent_i]
            _agent_i_obs = [pos[0] / self._grid_shape[0], pos[1] / (self._grid_shape[1] - 1)]  # coordinates

            # add 3 x3 mask around the agent current location and share neighbours
            # ( in practice: this information may not be so critical since the map never changes)
            _agent_i_neighbour = np.zeros((3, 3))
            for r in range(pos[0] - 1, pos[0] + 2):
                for c in range(pos[1] - 1, pos[1] + 2):
                    if self.is_valid((r, c)) and r != pos[0] and c != pos[1]:
                        item = 0
                        if PRE_IDS['lemon'] in self._full_obs[r][c]:
                            item = 1
                        elif PRE_IDS['apple'] in self._full_obs[r][c]:
                            item = 2
                        elif PRE_IDS['agent'] in self._full_obs[r][c]:
                            item = 3
                        elif PRE_IDS['wall'] in self._full_obs[r][c]:
                            item = -1
                        _agent_i_neighbour[r - (pos[0] - 1)][c - (pos[1] - 1)] = item
            _agent_i_obs += _agent_i_neighbour.flatten().tolist()

            # adding time
            _agent_i_obs += [self._step_count / self._max_steps]
            _obs.append(_agent_i_obs)

        if self.full_observable:
            _obs = np.array(_obs).flatten().tolist()
            _obs = [_obs for _ in range(self.n_agents)]
        return _obs

    def reset(self):
        self.__init_full_obs()
        self._step_count = 0
        self.__total_episode_reward = 0
        self._food_count = {'lemon': ((self._grid_shape[1] - 2) // 2) * self._grid_shape[0],
                            'apple': ((self._grid_shape[1] - 2) // 2) * self._grid_shape[0]}
        self._agent_dones = [False for _ in range(self.n_agents)]

        return self.get_agent_obs()

    def is_valid(self, pos):
        return (0 <= pos[0] < self._grid_shape[0]) and (0 <= pos[1] < self._grid_shape[1])

    def _is_cell_vacant(self, pos):
        return self.is_valid(pos) and (PRE_IDS['agent'] not in self._full_obs[pos[0]][pos[1]])

    def __update_agent_pos(self, agent_i, move):

        curr_pos = copy.copy(self.agent_pos[agent_i])
        if move == 0:  # down
            next_pos = [curr_pos[0] + 1, curr_pos[1]]
        elif move == 1:  # left
            next_pos = [curr_pos[0], curr_pos[1] - 1]
        elif move == 2:  # up
            next_pos = [curr_pos[0] - 1, curr_pos[1]]
        elif move == 3:  # right
            next_pos = [curr_pos[0], curr_pos[1] + 1]
        elif move == 4:  # no-op
            next_pos = None
        else:
            raise Exception('Action Not found!')

        self.agent_prev_pos[agent_i] = self.agent_pos[agent_i]
        if next_pos is not None and self._is_cell_vacant(next_pos):
            self.agent_pos[agent_i] = next_pos

    def __update_agent_view(self, agent_i):
        self._full_obs[self.agent_pos[agent_i][0]][self.agent_pos[agent_i][1]] = PRE_IDS['agent'] + str(agent_i + 1)

    def step(self, agents_action):
        assert len(agents_action) == self.n_agents

        self._step_count += 1
        rewards = [self._step_cost for _ in range(self.n_agents)]

        for agent_i, action in enumerate(agents_action):

            # for row in self._full_obs:
            #     print(row)
            # print('*********')

            self.__update_agent_pos(agent_i, action)

            if self.agent_pos[agent_i] != self.agent_prev_pos[agent_i]:
                for food in ['lemon', 'apple']:
                    if PRE_IDS[food] in self._full_obs[self.agent_pos[agent_i][0]][self.agent_pos[agent_i][1]]:
                        rewards[agent_i] += self.agent_reward[agent_i][food]
                        self._food_count[food] -= 1
                        break

                self._full_obs[self.agent_prev_pos[agent_i][0]][self.agent_prev_pos[agent_i][1]] = PRE_IDS['empty']
                self.__update_agent_view(agent_i)

            # for row in self._full_obs:
            #     print(row)
            # print('*********#')
            # print(self.agent_pos,self.agent_prev_pos)

        if self._step_count >= self._max_steps or self.no_food_left():
            for i in range(self.n_agents):
                self._agent_dones[i] = True

        # for row in self._full_obs:
        #     print(row)
        # print('*********')

        return self.get_agent_obs(), rewards, self._agent_dones, {'food_count': self._food_count}

    def no_food_left(self):
        return sum([v for k, v in self._food_count.items()]) == 0

    def __get_neighbour_coordinates(self, pos):
        neighbours = []
        if self.is_valid([pos[0] + 1, pos[1]]):
            neighbours.append([pos[0] + 1, pos[1]])
        if self.is_valid([pos[0] - 1, pos[1]]):
            neighbours.append([pos[0] - 1, pos[1]])
        if self.is_valid([pos[0], pos[1] + 1]):
            neighbours.append([pos[0], pos[1] + 1])
        if self.is_valid([pos[0], pos[1] - 1]):
            neighbours.append([pos[0], pos[1] - 1])
        return neighbours

    def render(self, mode='human'):
        for agent_i in range(self.n_agents):
            fill_cell(self._base_img, self.agent_pos[agent_i], cell_size=CELL_SIZE, fill='white', margin=0.05)
            fill_cell(self._base_img, self.agent_prev_pos[agent_i], cell_size=CELL_SIZE, fill='white', margin=0.05)
            draw_circle(self._base_img, self.agent_pos[agent_i], cell_size=CELL_SIZE, fill=AGENT_COLORS[agent_i])

        img = np.asarray(self._base_img)
        if mode == 'rgb_array':
            return img
        elif mode == 'human':
            from gym.envs.classic_control import rendering
            if self.viewer is None:
                self.viewer = rendering.SimpleImageViewer()
            self.viewer.imshow(img)
            return self.viewer.isopen

    def seed(self, n):
        self.np_random, seed1 = seeding.np_random(n)
        seed2 = seeding.hash_seed(seed1 + 1) % 2 ** 31
        return [seed1, seed2]

    def close(self):
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None


CELL_SIZE = 30

ACTION_MEANING = {
    0: "DOWN",
    1: "LEFT",
    2: "UP",
    3: "RIGHT",
    4: "NOOP",
}

# each pre-id should be unique and single char
PRE_IDS = {
    'agent': 'A_',
    'prey': 'P',
    'wall': 'W',
    'empty': '0',
    'lemon': 'L',
    'apple': 'K',
}

AGENT_COLORS = {
    0: 'red',
    1: 'blue'
}
WALL_COLOR = 'black'
LEMON_COLOR = 'yellow'
APPLE_COLOR = 'green'