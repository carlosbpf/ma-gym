import os
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, join_room, leave_room, emit
from threading import Lock
import base64
import queue
from queue import Queue, LifoQueue, Empty, Full
from PIL import Image
from io import BytesIO
from utils import ThreadSafeDict, ThreadSafeSet
import time

import argparse

import gym

from ma_gym.wrappers import Monitor

MAX_GAMES = 10
# 1 is for stop 0 to GO
DEFAULT_ACTION = 1

# Global queue of available IDs. This is how we synch game creation and keep track of how many games are in memory
FREE_IDS = queue.Queue(maxsize=MAX_GAMES)

# Bitmap that indicates whether ID is currently in use. Game with ID=i is "freed" by setting FREE_MAP[i] = True
FREE_MAP = ThreadSafeDict()

# Initialize our ID tracking data
for i in range(MAX_GAMES):
    FREE_IDS.put(i)
    FREE_MAP[i] = True

# Mapping of game-id to game objects
GAMES = ThreadSafeDict()

# Set of games IDs that are currently being played
ACTIVE_GAMES = ThreadSafeSet()

# Mapping of users to locks associated with the ID. Enforces user-level serialization
SUBJECTS = ThreadSafeDict()

# Mapping of user id's to the current game (room) they are in
SUBJECT_ROOMS = ThreadSafeDict()

ROOMS = ThreadSafeDict()

#######################
# Flask Configuration #
#######################

# Create and configure flask app
app = Flask(__name__, template_folder=os.path.join('static', 'templates'))
app.config['SECRET_KEY'] = 'secret!'
app.config["CACHE_TYPE"] = "null"
app.config['DEBUG'] = os.getenv('FLASK_ENV', 'production') == 'development'
socketio = SocketIO(app, cors_allowed_origins="*", logger=app.config['DEBUG'])
STEP_SLEEP_DURATION = 3

@app.route('/<room_id>/<subject_name>')
def index(room_id, subject_name):
    if room_id not in ROOMS:
        print('Setting up room: ' + room_id)
        env = gym.make('ma_gym:{}'.format(args.env))
        # env = Monitor(env, directory='recordings', force=True)
        try:
            curr_id = FREE_IDS.get(block=False)
            assert FREE_MAP[curr_id], "Current id is already in use"
        except queue.Empty:
            err = RuntimeError("Server at max capacity")
            return None, err
        except Exception as e:
            return None, e
        else:
            game = GameWrapper(env, curr_id, room_id)
            GAMES[curr_id] = game
            FREE_MAP[curr_id] = False
            ROOMS[room_id] = game

    return render_template('index.html', async_mode=socketio.async_mode, header_text='This is the traffic junction', default_action='breakOn')

@socketio.on('connect')
def on_connect():
    user_id = request.sid

    if user_id in SUBJECTS:
        return
    SUBJECTS[user_id] = Lock()

@socketio.on('join')
def on_join(data):
    user_id = request.sid
    room_id = data.get("room_id", 0)
    set_curr_room(user_id, room_id)
    print('Joining user : ' + user_id + ' at room: ' + room_id)
    with SUBJECTS[user_id]:
        game = get_curr_game(user_id)
        join_room(room_id)
        with game.lock:
            idx = game.add_subject(user_id)
            if game.subjects_checked_in() == 4:
                socketio.start_background_task(play_game, game)
            else:
                socketio.emit('waiting_game')
AGENTS_COLORS = [
    "red",
    "blue",
    "yellow",
    "orange",
    "black",
    "green",
    "purple",
    "pink",
    "brown",
    "grey"
]
def play_game(game):
    env = game.env
    for ep_i in range(args.episodes):
        done_n = [False for _ in range(env.n_agents)]
        ep_reward = 0

        obs_n = env.reset()
        setup = env.get_agent_setup();
        for agent_i in range(env.n_agents):
            socketio.emit('game_setup',
                           {"socket_id": game.players[agent_i], "index": agent_i, "start": '',
                            "origin": setup[agent_i]["origin"],
                            "route": setup[agent_i]["route"],
                            "color": AGENTS_COLORS[agent_i]})
            print('game_setup',
                          {"socket_id": game.players[agent_i], "index": agent_i, "start": '',
                           "origin": setup[agent_i]["origin"],
                           "route": setup[agent_i]["route"],
                           "color": AGENTS_COLORS[agent_i]})
            # print({"socket_id": game.players[agent_i], "index": agent_i, "start": '',
            #                 "destination": destinations[agent_i],
            #                 "color": AGENTS_COLORS[agent_i]})

        socketio.emit('start_game_episode', {"episonde": ep_i})

        game_board = env.render(mode='rgb_array')
        while not all(done_n):
            game.is_active = True
            #action_n = [int(_) for _ in input('Action:')]
            ## BOTS game.pending_actions
            ## SUBJECT
            action_n = [];
            for agent_i in range(len(game.players)):

                if game.pending_actions[agent_i].qsize() != 0:
                    action = game.pending_actions[agent_i].get(block=False)
                else:
                    action = game.last_actions[agent_i]
                print('Actions for subject {} this step: {}'.format(agent_i, action))
                action_n.append(action)
            # action_n = [0,0,0,0]
            obs_n, reward_n, done_n, _ = env.step(action_n)
            ep_reward += sum(reward_n)
            game_board = env.render(mode='rgb_array')
            png_img = Image.fromarray(game_board, "RGB")
            im_file = BytesIO()
            png_img.save(im_file, format="png")
            im_bytes = im_file.getvalue()  # im_bytes: image in binary format.
            im_b64 = base64.b64encode(im_bytes)
            base64str = im_b64.decode('utf-8')
            socketio.emit('game_board_update', {"state": base64str}, room=game.room_id)
            time.sleep(STEP_SLEEP_DURATION)

        # print('Episode #{} Reward: {}'.format(ep_i, ep_reward))
    env.close()

def set_curr_room(user_id, room_id):
    SUBJECT_ROOMS[user_id] = room_id
def get_game(game_id):
    return ROOMS.get(game_id, None)

def get_curr_game(user_id):
    return get_game(get_curr_room(user_id))

def get_curr_room(user_id):
    return SUBJECT_ROOMS.get(user_id, None)

@socketio.on('action')
def on_action(data):
    user_id = request.sid
    action = data['action']
    print('>>>>>>>>>>>> Got action {} from user_id {}'.format(action, user_id))
    game = get_curr_game(user_id)
    if not game:
        print('GAME NOT FOUND FOR user_id {}'.format(user_id))
        return

    game.enqueue_action(user_id, action)

@socketio.on('disconnect')
def on_disconnect():
    # Ensure game data is properly cleaned-up in case of unexpected disconnect
    user_id = request.sid
    if user_id not in SUBJECTS:
        return
    # with SUBJECTS[user_id]:
        # _leave_game(user_id)

    del SUBJECTS[user_id]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Interactive Server for ma-gym')
    parser.add_argument('--env', default='TrafficJunction4-v0',
                        help='Name of the environment (default: %(default)s)')
    parser.add_argument('--episodes', type=int, default=1,
                        help='episodes (default: %(default)s)')
    args = parser.parse_args()

class GameWrapper():
    def __init__(self, enviroment, id_number, room_id):
        self.id = id_number
        self.room_id = room_id
        self.players = []
        self.env = enviroment
        self.lock = Lock()
        self.is_active = False
        self.pending_actions = []
        self.last_actions = []

    def subjects_checked_in(self):
        return len(self.players)

    def subject_initial_setup_data(self, idx):
        setup = self.env.get_agent_setup()
        return setup[0][idx], setup[1][idx], setup[2][idx]

    def add_subject(self, player_id):
        idx = len(self.players)
        print('Index for player: ' + str(idx))
        self.players.append(player_id)
        self.pending_actions.append(Queue(maxsize=-1))
        self.last_actions.append(DEFAULT_ACTION)
        return idx

    def enqueue_action(self, player_id, action):
        """
        Add (player_id, action) pair to the pending action queue, without modifying underlying game state

        Note: This function IS thread safe
        """
        if not self.is_active:
            # Could run into issues with is_active not being thread safe
            return
        if player_id not in self.players:
            # Only players actively in game are allowed to enqueue actions
            return
        try:
            player_idx = self.players.index(player_id)
            print('Adding pending action to subject {}: {} '.format(player_idx, action))
            self.pending_actions[player_idx].put(action)
            self.last_actions[player_idx] = action

        except Full:
            pass
socketio.run(app, log_output=app.config['DEBUG'])
