import logging
import gym
from gym import error, spaces, utils
from gym.utils import seeding
import numpy as np
from ..utils import draw_grid, fill_cell, draw_cell_outline, draw_circle
import copy
import random

logger = logging.getLogger(__name__)


class PredatorPrey(gym.Env):
    """
    A simple environment to cross over the path of the other agent  (collaborative)

    Observation Space : Discrete
    Action Space : Discrete
    """
    metadata = {'render.modes': ['human']}

    def __init__(self):
        self.obs_size = 1
        self._grid_shape = (5, 5)
        self.n_agents = 2
        self.n_preys = 1
        self._max_steps = 100
        self._step_count = None

        self.action_space = [spaces.Discrete(5) for _ in range(2)]
        self.agent_pos = {}
        self.prey_pos = {}

        self._base_grid = self.__create_grid()  # with no agents
        self._full_obs = self.__create_grid()
        self._agent_dones = [False for _ in range(self.n_agents)]
        self._alive_preys = [True for _ in range(self.n_preys)]
        self._prey_move_probs = [0.2, 0.2, 0.2, 0.2, 0.2]
        self.viewer = None

    def __draw_base_img(self):
        self._base_img = draw_grid(self._grid_shape[0], self._grid_shape[1], cell_size=CELL_SIZE, fill='white')

    def __create_grid(self):
        _grid = [[PRE_IDS['empty'] for col in range(self._grid_shape[1])] for row in range(self._grid_shape[0])]
        return _grid

    def __init_full_obs(self):
        self._full_obs = self.__create_grid()

        for agent_i in range(self.n_agents):
            while True:
                pos = [random.randint(0, self._grid_shape[0] - 1), random.randint(0, self._grid_shape[1] - 1)]
                if self._is_cell_vacant(pos):
                    self.agent_pos[agent_i] = pos
                    break
            self.__update_agent_view(agent_i)

        for prey_i in range(self.n_preys):
            while True:
                pos = [random.randint(0, self._grid_shape[0] - 1), random.randint(0, self._grid_shape[1] - 1)]
                if self._is_cell_vacant(pos) and (self._neighbour_agents(pos)[0] == 0):
                    self.prey_pos[prey_i] = pos
                    break
            self.__update_prey_view(prey_i)

        self.__draw_base_img()

    def get_agent_obs(self):
        _obs = []
        for agent_i in range(0, self.n_agents):
            pos = self.agent_pos[agent_i]
            _agent_i_obs = [pos[0] / self._grid_shape[0], pos[1] / (self._grid_shape[1] - 1)]  # coordinates

            # check if prey is in neighbour
            _prey_pos = [0 for _ in range(4)]  # prey location in neighbour
            if self.is_valid([pos[0] + 1, pos[1]]) and PRE_IDS['prey'] in self._full_obs[pos[0] + 1][pos[1]]:
                _prey_pos[0] = 1
            if self.is_valid([pos[0] - 1, pos[1]]) and PRE_IDS['prey'] in self._full_obs[pos[0] - 1][pos[1]]:
                _prey_pos[1] = 1
            if self.is_valid([pos[0], pos[1] + 1]) and PRE_IDS['prey'] in self._full_obs[pos[0]][pos[1] + 1]:
                _prey_pos[2] = 1
            if self.is_valid([pos[0], pos[1] - 1]) and PRE_IDS['prey'] in self._full_obs[pos[0]][pos[1] - 1]:
                _prey_pos[3] = 1

            _agent_i_obs += _prey_pos
            _obs.append(_agent_i_obs)
        return _obs

    def reset(self):
        self.agent_pos = {}
        self.prey_pos = {}

        self.__init_full_obs()
        self._step_count = 0
        self._agent_dones = [False for _ in range(self.n_agents)]
        self._alive_preys = [True for _ in range(self.n_preys)]
        return self.get_agent_obs()

    def __wall_exists(self, pos):
        row, col = pos
        return PRE_IDS['wall'] in self._base_grid[row, col]

    def is_valid(self, pos):
        return (0 <= pos[0] < self._grid_shape[0]) and (0 <= pos[1] < self._grid_shape[1])

    def _is_cell_vacant(self, pos):
        return self.is_valid(pos) and (self._full_obs[pos[0]][pos[1]] == PRE_IDS['empty'])

    def __update_agent_pos(self, agent_i, move):
        curr_pos = copy.copy(self.agent_pos[agent_i])
        next_pos = None
        if move == 0:  # down
            next_pos = [curr_pos[0] + 1, curr_pos[1]]
        elif move == 1:  # left
            next_pos = [curr_pos[0], curr_pos[1] - 1]
        elif move == 2:  # up
            next_pos = [curr_pos[0] - 1, curr_pos[1]]
        elif move == 3:  # right
            next_pos = [curr_pos[0], curr_pos[1] + 1]
        elif move == 4:  # no-op
            pass
        else:
            raise Exception('Action Not found!')

        if next_pos is not None and self._is_cell_vacant(next_pos):
            self.agent_pos[agent_i] = next_pos
            self._full_obs[curr_pos[0]][curr_pos[1]] = PRE_IDS['empty']
            self.__update_agent_view(agent_i)

    def __next_pos(self, curr_pos, move):
        if move == 0:  # down
            next_pos = [curr_pos[0] + 1, curr_pos[1]]
        elif move == 1:  # left
            next_pos = [curr_pos[0], curr_pos[1] - 1]
        elif move == 2:  # up
            next_pos = [curr_pos[0] - 1, curr_pos[1]]
        elif move == 3:  # right
            next_pos = [curr_pos[0], curr_pos[1] + 1]
        elif move == 4:  # no-op
            next_pos = curr_pos
        return next_pos

    def __update_prey_pos(self, prey_i, move):
        curr_pos = copy.copy(self.prey_pos[prey_i])
        next_pos = None
        if move == 0:  # down
            next_pos = [curr_pos[0] + 1, curr_pos[1]]
        elif move == 1:  # left
            next_pos = [curr_pos[0], curr_pos[1] - 1]
        elif move == 2:  # up
            next_pos = [curr_pos[0] - 1, curr_pos[1]]
        elif move == 3:  # right
            next_pos = [curr_pos[0], curr_pos[1] + 1]
        elif move == 4:  # no-op
            pass
        else:
            raise Exception('Action Not found!')

        if next_pos is not None and self._is_cell_vacant(next_pos):
            self.prey_pos[prey_i] = next_pos
            self._full_obs[curr_pos[0]][curr_pos[1]] = PRE_IDS['empty']
            self.__update_prey_view(prey_i)
        else:
            pass

    def __update_agent_view(self, agent_i):
        self._full_obs[self.agent_pos[agent_i][0]][self.agent_pos[agent_i][1]] = PRE_IDS['agent'] + str(agent_i + 1)

    def __update_prey_view(self, prey_i):
        self._full_obs[self.prey_pos[prey_i][0]][self.prey_pos[prey_i][1]] = PRE_IDS['prey'] + str(prey_i + 1)

    def __is_agent_done(self, agent_i):
        return self.agent_pos[agent_i] == self.final_agent_pos[agent_i]

    def _neighbour_agents(self, pos):
        # check if agent is in neighbour
        _count = 0
        neighbours_xy = []
        if self.is_valid([pos[0] + 1, pos[1]]) and PRE_IDS['agent'] in self._full_obs[pos[0] + 1][pos[1]]:
            _count += 1
            neighbours_xy.append([pos[0] + 1, pos[1]])
        if self.is_valid([pos[0] - 1, pos[1]]) and PRE_IDS['agent'] in self._full_obs[pos[0] - 1][pos[1]]:
            _count += 1
            neighbours_xy.append([pos[0] - 1, pos[1]])
        if self.is_valid([pos[0], pos[1] + 1]) and PRE_IDS['agent'] in self._full_obs[pos[0]][pos[1] + 1]:
            _count += 1
            neighbours_xy.append([pos[0], pos[1] + 1])
        if self.is_valid([pos[0], pos[1] - 1]) and PRE_IDS['agent'] in self._full_obs[pos[0]][pos[1] - 1]:
            neighbours_xy.append([pos[0], pos[1] - 1])
            _count += 1

        agent_id = []
        for x, y in neighbours_xy:
            agent_id.append(int(self._full_obs[x][y].split(PRE_IDS['agent'])[1]) - 1)
        return _count, agent_id

    def step(self, one_hot_actions):
        self._step_count += 1
        rewards = [0 for _ in range(self.n_agents)]

        for agent_i, action in enumerate(one_hot_actions):
            action = action.index(1)
            if not (self._agent_dones[agent_i]):
                self.__update_agent_pos(agent_i, action)

        for prey_i in range(self.n_preys):
            if self._alive_preys[prey_i]:
                predator_neighbour_count, n_i = self._neighbour_agents(self.prey_pos[prey_i])

                if predator_neighbour_count > 0:
                    if predator_neighbour_count >= 2:
                        self._alive_preys[prey_i] = False
                        pos = self.prey_pos[prey_i]
                        self._full_obs[pos[0]][pos[1]] = PRE_IDS['empty']
                        _reward = 1
                    elif predator_neighbour_count == 1:
                        _reward = -0.5

                    for agent_i in n_i:
                        rewards[agent_i] += _reward
                else:
                    prey_move = None
                    for _ in range(5):
                        _move = np.random.choice(len(self._prey_move_probs), 1, p=self._prey_move_probs)[0]
                        if self._neighbour_agents(self.__next_pos(self.prey_pos[prey_i], _move))[0] == 0:
                            prey_move = _move
                            break
                    prey_move = 4 if prey_move is None else prey_move  # default is no-op(4)
                    self.__update_prey_pos(prey_i, prey_move)

        if self._step_count >= self._max_steps:
            for i in range(self.n_agents):
                self._agent_dones[i] = True

        # for row in self._full_obs:
        #     print(row)
        # print('***************')

        return self.get_agent_obs(), rewards, self._agent_dones, {}

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
        img = copy.copy(self._base_img)
        for agent_i in range(self.n_agents):
            draw_circle(img, self.agent_pos[agent_i], cell_size=CELL_SIZE, fill=AGENT_COLOR)
            for neighbour in self.__get_neighbour_coordinates(self.agent_pos[agent_i]):
                draw_cell_outline(img, neighbour, cell_size=CELL_SIZE, fill=AGENT_COLOR)
        for prey_i in range(self.n_preys):
            draw_circle(img, self.prey_pos[prey_i], cell_size=CELL_SIZE, fill=PREY_COLOR)
        img = np.asarray(img)

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


AGENT_COLOR = 'blue'
PREY_COLOR = 'red'

CELL_SIZE = 40

WALL_COLOR = 'black'

ACTION_MEANING = {
    0: "DOWN",
    1: "LEFT",
    2: "UP",
    3: "RIGHT",
    4: "NOOP",
}

PRE_IDS = {
    'agent': 'A',
    'prey': 'P',
    'wall': 'W',
    'empty': '0'
}
