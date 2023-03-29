import os
os.sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
os.environ['MESA_GL_VERSION_OVERRIDE'] = '3.3'
os.environ['MESA_GLSL_VERSION_OVERRIDE'] = '330'
import numpy as np
import torch
from torch.optim import Adam
import gym
import time
from utils.logx import EpochLogger, setup_logger_kwargs, colorize
from safety_gym.envs.engine import Engine as safety_gym_Engine
from safety_gym_arm.envs.engine import Engine as safety_gym_arm_Engine
from utils.safetygym_config import configuration
import os.path as osp
import cv2
import matplotlib.pyplot as plt
from mujoco_py import GlfwContext

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")



def create_env(args):
    if 'My' not in args.task:
        env = safety_gym_arm_Engine(configuration(args.task, args))
    else:
        env = safety_gym_Engine(configuration(args.task, args))
    return env


def replay(env_fn, model_path=None, video_name=None, max_epoch=1):
    if not model_path:
        print("please specify a model path")
        raise NotImplementedError
    if not video_name:
        print("please specify a video name")
        raise NotImplementedError    
    
    # Instantiate environment
    env = env_fn()
    
    # reset environment
    o = env.reset()
    d = False
    ep_ret = 0
    time_step = 0
    epoch = 0
    M = 0. # initialize the current maximum cost
    o_aug = np.append(o, M) # augmented observation = observation + M 
    first_step = True
    
    video_array = []
    
    # load the model 
    ac = torch.load(model_path)
    
    # evaluate the model 
    while True:
        time_step += 1
        if d:
            epoch += 1
            print('Episode Return: %.3f'%(ep_ret))
            if epoch == max_epoch:
                env.close()
                break
            ep_ret = 0
            o = env.reset()
            M = 0. # initialize the current maximum cost 
            # o_aug = o.append(M) # augmented observation = observation + M 
            o_bug = np.append(o, M) # augmented observation = observation + M 
            first_step = True
        
        try:
            a, v, vc, logp, _, _ = ac.step(torch.as_tensor(o_aug, dtype=torch.float32))
        except:
            print('please choose the correct environment, the observation space doesn''t match')
            raise NotImplementedError
        

        next_o, r, d, info = env.step(a)
        
        if first_step:
            # the first step of each episode 
            cost_increase = info['cost']
            M_next = info['cost']
            first_step = False
        else:
            # the second and forward step of each episode
            cost_increase = max(info['cost'] - M, 0)
            M_next = M + cost_increase 
        
        # Update obs (critical!)
        # o = next_o
        o_aug = np.append(next_o, M_next)

        img_array = env.render(mode='rgb_array')
        video_array.append(img_array)

        ep_ret += r

    # save video 
    fps = 60
    dsize = (1920,1080)
    out_path = '../video'
    existence = os.path.exists(out_path)
    if not existence:
        os.makedirs(out_path)
    video_writer = cv2.VideoWriter(os.path.join(out_path,f'{video_name}.mp4'),
                                cv2.VideoWriter_fourcc(*'FMP4'), fps, dsize)

    for frame in video_array:
        resized = cv2.resize(frame, dsize=dsize)
        video_writer.write(resized)

    video_writer.release()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()    
    parser.add_argument('--task', type=str, default='Mygoal4')
    parser.add_argument('--hazards_size', type=float, default=0.30)  # the default hazard size of safety gym 
    parser.add_argument('--max_epoch', type=int, default=1)  # the maximum number of epochs
    parser.add_argument('--model_path', type=str, default=None)
    parser.add_argument('--video_name', type=str, default=None)
    args = parser.parse_args()

    replay(lambda : create_env(args), model_path=args.model_path, video_name=args.video_name, max_epoch=args.max_epoch)