import os
import gym
import torch
import pickle
import pprint
import argparse
import numpy as np
from torch.utils.tensorboard import SummaryWriter

from tianshou.data import Collector
from tianshou.utils import TensorboardLogger
from tianshou.env import DummyVectorEnv
from tianshou.utils.net.common import Net
from tianshou.trainer import offline_trainer
from tianshou.policy import DiscreteCRRPolicy


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, default="CartPole-v0")
    parser.add_argument("--seed", type=int, default=1626)
    parser.add_argument("--lr", type=float, default=7e-4)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--n-step", type=int, default=3)
    parser.add_argument("--target-update-freq", type=int, default=320)
    parser.add_argument("--epoch", type=int, default=5)
    parser.add_argument("--update-per-epoch", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument('--hidden-sizes', type=int,
                        nargs='*', default=[64, 64])
    parser.add_argument("--test-num", type=int, default=100)
    parser.add_argument("--logdir", type=str, default="log")
    parser.add_argument("--render", type=float, default=0.)
    parser.add_argument(
        "--load-buffer-name", type=str,
        default="./expert_DQN_CartPole-v0.pkl",
    )
    parser.add_argument(
        "--device", type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    args = parser.parse_known_args()[0]
    return args


def test_discrete_crr(args=get_args()):
    # envs
    env = gym.make(args.task)
    if args.task == 'CartPole-v0':
        env.spec.reward_threshold = 190  # lower the goal
    args.state_shape = env.observation_space.shape or env.observation_space.n
    args.action_shape = env.action_space.shape or env.action_space.n
    test_envs = DummyVectorEnv(
        [lambda: gym.make(args.task) for _ in range(args.test_num)])
    # seed
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    test_envs.seed(args.seed)
    # model
    actor = Net(args.state_shape, args.action_shape,
                hidden_sizes=args.hidden_sizes, device=args.device,
                softmax=False)
    critic = Net(args.state_shape, args.action_shape,
                 hidden_sizes=args.hidden_sizes, device=args.device,
                 softmax=False)
    optim = torch.optim.Adam(list(actor.parameters()) + list(critic.parameters()),
                             lr=args.lr)

    policy = DiscreteCRRPolicy(
        actor, critic, optim, args.gamma,
        target_update_freq=args.target_update_freq,
    ).to(args.device)
    # buffer
    assert os.path.exists(args.load_buffer_name), \
        "Please run test_dqn.py first to get expert's data buffer."
    buffer = pickle.load(open(args.load_buffer_name, "rb"))

    # collector
    test_collector = Collector(policy, test_envs, exploration_noise=True)

    log_path = os.path.join(args.logdir, args.task, 'discrete_cql')
    writer = SummaryWriter(log_path)
    logger = TensorboardLogger(writer)

    def save_fn(policy):
        torch.save(policy.state_dict(), os.path.join(log_path, 'policy.pth'))

    def stop_fn(mean_rewards):
        return mean_rewards >= env.spec.reward_threshold

    result = offline_trainer(
        policy, buffer, test_collector,
        args.epoch, args.update_per_epoch, args.test_num, args.batch_size,
        stop_fn=stop_fn, save_fn=save_fn, logger=logger)

    assert stop_fn(result['best_reward'])

    if __name__ == '__main__':
        pprint.pprint(result)
        # Let's watch its performance!
        env = gym.make(args.task)
        policy.eval()
        collector = Collector(policy, env)
        result = collector.collect(n_episode=1, render=args.render)
        rews, lens = result["rews"], result["lens"]
        print(f"Final reward: {rews.mean()}, length: {lens.mean()}")


if __name__ == "__main__":
    test_discrete_crr(get_args())
