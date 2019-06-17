import gym
import ma_gym
from ma_gym.wrappers import Monitor
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Random Agent for ma-gym')
    parser.add_argument('--env', default='CrossOver-v0',
                        help='Name of the environment (default: %(default)s)')
    parser.add_argument('--episodes', type=int, default=2,
                        help='episodes (default: %(default)s)')
    args = parser.parse_args()

    env = gym.make(args.env)
    env = Monitor(env, directory='recordings', force=True)
    for ep_i in range(args.episodes):
        done_n = [False for _ in range(env.n_agents)]
        ep_reward = 0

        obs_n = env.reset()
        while not all(done_n):
            env.render()
            action_n = env.action_space.sample()
            obs_n, reward_n, done_n, _ = env.step(action_n)
            ep_reward += sum(reward_n)

        print('Episode #{} Reward: {}'.format(ep_i, ep_reward))
    env.close()