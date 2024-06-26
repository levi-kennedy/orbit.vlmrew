# Copyright (c) 2022-2024, The ORBIT Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Script to play a checkpoint if an RL agent from Stable-Baselines3."""

"""Launch Isaac Sim Simulator first."""

import argparse

from omni.isaac.orbit.app import AppLauncher

# add argparse arguments
parser = argparse.ArgumentParser(description="Play a checkpoint of an RL agent from Stable-Baselines3.")
parser.add_argument("--cpu", action="store_true", default=False, help="Use CPU pipeline.")
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
parser.add_argument("--num_envs", type=int, default=1, help="Number of environments to simulate.")
parser.add_argument("--task", type=str, default="Isaac-Lift-Cube-Franka-v0", help="Name of the task.")
parser.add_argument("--checkpoint", type=str, default=None, help="Path to model checkpoint.")
parser.add_argument(
    "--use_last_checkpoint",
    action="store_true",
    help="When no checkpoint provided, use the last saved model. Otherwise use the best saved model.",
)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# parse the arguments
args_cli = parser.parse_args()

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import gymnasium as gym 
import numpy as np
import os
import torch

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import VecNormalize

#import omni.isaac.orbit_tasks  # noqa: F401
from omni.isaac.orbit_tasks.utils.parse_cfg import get_checkpoint_path, load_cfg_from_registry, parse_env_cfg
from omni.isaac.orbit_tasks.utils.wrappers.sb3 import Sb3VecEnvWrapper, process_sb3_cfg
import yaml
from omni.isaac.orbit.envs import RLTaskEnv


def read_yaml_file(filepath):
    with open(filepath, "r") as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(exc)


def main():
    """Play with stable-baselines agent."""
    # parse configuration
    env_cfg = parse_env_cfg(
        args_cli.task, use_gpu=not args_cli.cpu, num_envs=args_cli.num_envs, use_fabric=not args_cli.disable_fabric
    )
    # env_cfg = LiftEnvCfg()
    env_cfg.scene.num_envs = args_cli.num_envs
    # setup RL environment
    env = RLTaskEnv(cfg=env_cfg)

    # turn off the frame marker for the end effector (huge pain!)
    frame_prim_path = '/Visuals/Command/body_pose/frame'
    env.scene.stage.GetPrimAtPath(frame_prim_path).GetAttribute('visibility').Set('invisible')

    agent_cfg_yaml_file_path = "/home/levi/projects/orbit.vlmrew/orbit/vlmrew/tasks/manipulation/lift/sb3_ppo_cfg.yaml"
    # Read in the yaml file
    agent_cfg = read_yaml_file(agent_cfg_yaml_file_path)

    # create isaac environment
    # env = gym.make(args_cli.task, cfg=env_cfg)
    # wrap around environment for stable baselines
    env = Sb3VecEnvWrapper(env)

    # normalize environment (if needed)
    if "normalize_input" in agent_cfg:
        env = VecNormalize(
            env,
            training=True,
            norm_obs="normalize_input" in agent_cfg and agent_cfg.pop("normalize_input"),
            norm_reward="normalize_value" in agent_cfg and agent_cfg.pop("normalize_value"),
            clip_obs="clip_obs" in agent_cfg and agent_cfg.pop("clip_obs"),
            gamma=agent_cfg["gamma"],
            clip_reward=np.inf,
        )

    # directory for logging into
    log_root_path = os.path.join("/home/levi/projects/orbit.vlmrew/logs", "sb3", args_cli.task)
    log_root_path = os.path.abspath(log_root_path)
    # check checkpoint is valid
    if args_cli.checkpoint is None:
        if args_cli.use_last_checkpoint:
            checkpoint = "model_.*.zip"
        else:
            checkpoint = "model.zip"
        checkpoint_path = get_checkpoint_path(log_root_path, ".*", checkpoint)
    else:
        checkpoint_path = args_cli.checkpoint

    # create agent from stable baselines
    print(f"Loading checkpoint from: {checkpoint_path}")
    agent = PPO.load(checkpoint_path, env, print_system_info=True)

    # reset environment
    obs = env.reset()
    
    # simulate environment
    while simulation_app.is_running():
        # run everything in inference mode
        with torch.inference_mode():
            # agent stepping
            actions, _ = agent.predict(obs, deterministic=True)
            # env stepping
            obs, _, _, _ = env.step(actions)

    # close the simulator
    env.close()


if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()
