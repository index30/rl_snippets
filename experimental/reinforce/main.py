"""One file REINFORCE algorithm."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import itertools

import collections
import gym
import numpy as np
import tensorflow as tf
from agents.tools.attr_dict import AttrDict
from agents.tools.wrappers import ConvertTo32Bit
from ray.experimental.tfutils import TensorFlowVariables
from ray.rllib.utils.filter import MeanStdFilter

Trajectory = collections.namedtuple('Trajectory',
                                    'observ, reward, done, action, next_observ, raw_return, return_')
Trajectory.__new__.__defaults__ = (None,) * len(Trajectory._fields)


class Policy(object):
    
    def __init__(self, sess: tf.Session, config):
        """Neural network policy that compute action given observation.
        
        Args:
            config: Useful configuration, almost use as const.
        """
        self.sess = sess
        
        self.config = config
        self._build_model()
        self._set_loss()
        optimizer = tf.train.GradientDescentOptimizer(config.learning_rate)
        grads_and_vars = optimizer.compute_gradients(self.loss)
        self.train_op = optimizer.apply_gradients(grads_and_vars)
        
        self.variables = TensorFlowVariables(self.loss, self.sess)
        self.sess.run(tf.global_variables_initializer())
    
    def _build_model(self):
        """Build TensorFlow policy model.
        """
        self.observ = tf.placeholder(tf.float32, (None, 2), name='observ')
        self.action = tf.placeholder(tf.float32, (None, 1), name='action')
        x = tf.layers.dense(self.observ, 100, use_bias=False)
        x = tf.layers.dense(x, 100, use_bias=False)
        x = tf.layers.dense(x, 1, use_bias=False)
        x = tf.clip_by_value(x, -1., 1.)
        self.model = x
    
    def _set_loss(self):
        # TODO: How to implement loss function.
        prob = tf.nn.softmax(self.model)
        prob = tf.exp(prob) - tf.exp(self.action)
        log_prob = -tf.log(prob)
        log_prob = tf.check_numerics(log_prob, 'log_prob')
        self.loss = log_prob
    
    def compute_action(self, observ):
        """Generate action from \pi(a_t | s_t) that is neural network.
        
        Args:
            observ: Observation generated by gym.Env.observation.

        Returns:
            (Lights, Camera) Action
        """
        assert observ.shape == (1, 2)
        action = self.sess.run(self.model, feed_dict={self.observ: observ})
        return action[0]


# TODO: I WILL IMPLEMENT.
class ValueFunction(object):
    
    def __init__(self, sess: tf.Session, config):
        """Neural network policy that compute action given observation.
        
        Args:
            config: Useful configuration, almost use as const.
        """
        self.sess = sess
        
        self.config = config
        self._build_model()
        self._set_loss()
        optimizer = tf.train.GradientDescentOptimizer(config.learning_rate)
        grads_and_vars = optimizer.compute_gradients(self.loss)
        self.train_op = optimizer.apply_gradients(grads_and_vars)
        
        self.variables = TensorFlowVariables(self.loss, self.sess)
        self.sess.run(tf.global_variables_initializer())
    
    def _build_model(self):
        pass


class REINFORCE(object):
    
    def __init__(self, config):
        tf.reset_default_graph()
        self.sess = tf.Session()
        
        env = gym.make(config.env_name)
        self.config = config
        self.env = ConvertTo32Bit(env)
        self.policy = Policy(sess=self.sess, config=config)
        
        self._init()
    
    def _init(self):
        self.reward_filter = MeanStdFilter((), clip=5.)
    
    def _train(self):
        episodes = []
        for _ in range(self.config.num_episodes):
            episode = rollouts(self.env,
                               self.policy,
                               self.reward_filter,
                               self.config)
            print(episode[0])
            episodes.append(episode)
        
        losses = []
        for episode in episodes:
            for trajectory in episode:
                _, loss = self.sess.run(
                    [self.policy.train_op, self.policy.loss], feed_dict={
                        self.policy.observ: trajectory.observ,
                        self.policy.action: trajectory.action})
                losses.append(loss)
                print('>> loss', loss)
        return losses
    
    def train(self, num_iters):
        for i in range(num_iters):
            losses = self._train()
            yield losses


def rollouts(env, policy: Policy, reward_filter: MeanStdFilter, config):
    """
    Args:
        env: OpenAI Gym wrapped by agents.wrappers
        policy(Policy): instance of Policy
        reward_filter(MeanStdFilter): Use ray's MeanStdFilter for calculate easier
        config: Useful configuration, almost use as const.

    Returns:
        1 episode(rollout) that is sequence of trajectory.
    """
    raw_return = 0
    return_ = 0
    observ = env.reset()
    observ = observ[np.newaxis, ...]
    
    trajectories = []
    for t in itertools.count():
        # a_t ~ pi(a_t | s_t)
        action = policy.compute_action(observ)
        
        next_observ, reward, done, _ = env.step(action)
        next_observ = next_observ[np.newaxis, ...]
        action = action[np.newaxis, ...]
        
        # Adjust reward
        reward = reward_filter(reward)
        raw_return += reward
        return_ += reward * config.discount_factor ** t
        
        trajectories.append(Trajectory(observ, reward, done, action, next_observ, raw_return, return_))
        observ = next_observ
        
        if done:
            break
    return trajectories


def default_config():
    use_bias = False
    env_name = 'MountainCarContinuous-v0'
    discount_factor = 0.995
    learning_rate = 1e-3
    num_episodes = 50
    
    return locals()

def test_config():
    use_bias = False
    env_name = 'MountainCarContinuous-v0'
    discount_factor = 0.995
    learning_rate = 1e-3
    num_episodes = 5
    
    return locals()


def test_main():
    reward_filter = MeanStdFilter((), clip=5.)
    reward_filter2 = MeanStdFilter((), clip=5.)
    config = AttrDict(default_config())
    env = gym.make(config.env_name)
    env = ConvertTo32Bit(env)
    sess = tf.Session()
    policy = Policy(sess, config)
    poli = Policy(sess, config)
    
    traj = rollouts(env, policy, reward_filter, config)
    traj2 = rollouts(env, poli, reward_filter2, config)
    print(traj[0])
    print(traj2[0])


def main(_):
    config = AttrDict(test_config())
    agent = REINFORCE(config)
    
    for losses in agent.train(num_iters=1):
        print('loss', losses[0], losses[-1])


if __name__ == '__main__':
    # test_main()
    tf.app.run()