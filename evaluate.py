import argparse
import torch
import os
import numpy as np
import time
from gym.spaces import Box, Tuple, Discrete
from pathlib import Path
from components.make_env import make_env
from components.arguments import get_common_args, get_mixer_args, get_coma_args, get_liir_args, get_maac_args
from agent.agent import Agents

import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('TkAgg')


def get_env_scheme(env):
    agent_init_params = []

    def get_shape(sp):
        space, dim = 0, 0
        if isinstance(sp, Box):
            space = sp.shape[0]
            dim = sp.shape[0]
        elif isinstance(sp, Tuple):
            for p in sp.spaces:
                if isinstance(p, Box):
                    space += p.shape[0]
                    dim += p.shape[0]
                else:
                    space += p.n
                    dim += 1
        else:  # if the instance is 'Discrete', the action dim is 1
            space = sp.n
            dim = 1
        return space, dim

    for acsp, obsp in zip(env.action_space, env.observation_space):
        observation_space, observation_dim = get_shape(obsp)
        action_space, action_dim = get_shape(acsp)
        agent_init_params.append({'observation_space': observation_space,
                                  'observation_dim': observation_dim,
                                  'action_space': action_space,
                                  'action_dim': action_dim})

    return agent_init_params


def runner(env, args):
    model_path = (Path('./models') / args.env_id / args.algo /
                  ('run%i' % args.run_num))
    if args.incremental is not None:
        model_path = model_path / 'incremental' / ('model_ep%i.pt' % args.incremental)
    else:
        model_path = model_path / 'model.pt'

    agents = Agents(args)
    agents.load(str(model_path))
    ifi = 1 / args.fps  # inter-frame interval

    for ep_i in range(args.n_evaluate_episodes):
        print("Episode %i of %i" % (ep_i + 1, args.n_evaluate_episodes))
        obs = env.reset()
        last_action = np.zeros((args.n_agents, args.n_actions))
        agents.policy.init_hidden(1)
        epsilon = 0
        step = 0

        if args.display or args.evaluate:
            env.render('human')

        while step < args.n_evaluate_steps:
            calc_start = time.time()
            obs = np.array(obs).reshape((args.n_agents, -1))
            actions, actions_onehot = [], []
            for agent_num in range(args.n_agents):
                action = agents.select_action(obs[agent_num], last_action[agent_num], agent_num, epsilon, args.evaluate)
                action_onehot = np.zeros(args.n_actions)
                action_onehot[action] = 1
                actions.append(action)
                actions_onehot.append(action_onehot)
                last_action[agent_num] = action_onehot

            obs, rewards, terminates, infos = env.step(actions_onehot)

            if args.display or args.evaluate:
                calc_end = time.time()
                elapsed = calc_end - calc_start
                if elapsed < ifi:
                    time.sleep(ifi - elapsed)
                env.render('human')

            step += 1

    env.close()


if __name__ == '__main__':
    args = get_common_args()
    if args.algo.find('vdn') > -1 or args.algo.find('qmix') > -1:
        args = get_mixer_args(args)
    elif args.algo.find('maac') > -1:
        args = get_maac_args(args)
    elif args.algo.find('liir') > -1:
        args = get_liir_args(args)
    else:
        args = get_coma_args(args)
    assert args.n_rollout_threads == 1, "For simple test, the environment are required for 1"
    env = make_env(args.env_id)
    scheme = get_env_scheme(env)
    args.n_agents = len(scheme)
    args.obs_shape = scheme[0]['observation_space']
    args.n_actions = scheme[0]['action_space']

    # Some hyper-parameters for evaluating
    args.evaluate = True
    args.run_num = 1
    args.incremental = None
    args.fps = 30
    args.n_evaluate_episodes = 10
    args.n_evaluate_steps = 50

    runner(env, args)

