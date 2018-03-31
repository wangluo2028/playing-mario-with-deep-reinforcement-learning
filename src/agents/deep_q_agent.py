"""An implementation of Deep Q-Learning."""
import numpy as np
import cv2
from tqdm import tqdm
from typing import Callable
from src.models import build_deep_mind_model
from .agent import Agent
from .replay_queue import ReplayQueue


# the format string for this objects representation
_REPR_TEMPLATE = """
{}(
    env={},
    learning_rate={},
    discount_factor={},
    exploration_rate={},
    exploration_decay={},
    exploration_min={},
    image_size={},
    frames_per_action={},
    replay_size={}
)
""".lstrip()


class DeepQAgent(Agent):
    """
    An implementation of Deep Q-Learning.

    Algorithm:
        initialize Q[s, a]
        observe initial state s
        while not done:
          select and perform an action a
          observe a reward r and new state s'
          Q[s, a] ←  Q[s, a] + α(r + γ max_a'(Q[s', a']) - Q[s, a])
          s ← s'

    Note:
    -   when α = 1, this reduces to vanilla Bellman Equation
      -   Q[s, a] ← r + γmax_a'(Q[s', a'])
    -   another formulation uses the probabilistic inverse of the
        learning rate as a factor for original Q value:
      -   Q[s, a] ←  (1 - α)Q[s, a] + α(r + γ max_a'(Q[s', a']) - Q[s, a])

    """

    def __init__(self,
                 env,
                 learning_rate: float=0.001,
                 discount_factor: float=0.99,
                 exploration_rate: float=1.0,
                 exploration_decay: float=0.9998,
                 exploration_min: float=0.1,
                 image_size: tuple=(84, 84),
                 frames_per_action: int=4,
                 replay_size: int=20000
        ) -> None:
        """
        Initialize a new Deep Q Agent.

        Args:
            env: the environment to run on
            learning_rate: the learning rate, α
            discount_factor: the discount factor, γ
            exploration_rate: the exploration rate, ε
            exploration_decay: the decay factor for exploration rate
            exploration_min: the minimum value for the exploration rate
            frames_per_action: the number of frames to hold an action
            replay_size: the

        Returns: None
        """
        # TODO: validate env type

        # verify learning_rate
        if not isinstance(learning_rate, float):
            raise TypeError('learning_rate must be of type float')
        if learning_rate < 0:
            raise ValueError('learning_rate must be positive')
        # verify discount_factor
        if not isinstance(discount_factor, float):
            raise TypeError('discount_factor must be of type float')
        if discount_factor < 0:
            raise ValueError('discount_factor must be positive')
        # verify exploration_rate
        if not isinstance(exploration_rate, float):
            raise TypeError('exploration_rate must be of type float')
        if not 0 <= exploration_rate <= 1:
            raise ValueError('exploration_rate must be in [0,1]')
        # verify exploration_decay
        if not isinstance(exploration_decay, float):
            raise TypeError('exploration_decay must be of type float')
        if exploration_decay < 0:
            raise ValueError('exploration_decay must be positive')
        # verify exploration_min
        if not isinstance(exploration_min, float):
            raise TypeError('exploration_min must be of type float')
        if exploration_min < 0:
            raise ValueError('exploration_min must be positive')
        # verify image_size
        if not isinstance(image_size, tuple):
            raise TypeError('image_size must be of type tuple')
        if len(image_size) != 2:
            raise ValueError('image_size must be a tuple of two integers')
        # verify frames_per_action
        if not isinstance(frames_per_action, int):
            raise TypeError('frames_per_action must be of type int')
        if frames_per_action < 1:
            raise ValueError('frames_per_action must be >= 1')
        # assign arguments to self
        self.env = env
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.exploration_decay = exploration_decay
        self.exploration_min = exploration_min
        self.image_size = image_size
        self.frames_per_action = frames_per_action
        # setup other instance members
        self.model = build_deep_mind_model(
            image_size=image_size,
            num_frames=frames_per_action,
            num_actions=env.action_space.n,
            learning_rate=learning_rate
        )
        self.queue = ReplayQueue(replay_size)

    def __repr__(self) -> str:
        """Return a debugging string of this agent."""
        return _REPR_TEMPLATE.format(
            self.__class__.__name__,
            self.env,
            self.learning_rate,
            self.discount_factor,
            self.exploration_rate,
            self.exploration_decay,
            self.exploration_min,
            self.image_size,
            self.frames_per_action,
            self.queue.size
        )

    @property
    def input_shape(self) -> tuple:
        """Return the input shape of the DQN."""
        return (1, *self.model.input_shape[1:])

    @property
    def num_actions(self) -> int:
        """Return the number of actions for this agent."""
        return self.model.output_shape[1]

    def _downsample(self, frame: np.ndarray) -> np.ndarray:
        """
        Down-sample the given frame from RGB to B&W with a reduced size.

        Args:
            frame: the frame to down-sample

        Returns:
            a down-sample B&W frame

        """
        return cv2.resize(cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY), self.image_size)

    def predict_action(self, frames: np.ndarray) -> tuple:
        """
        Predict an action from a stack of frames.

        Args:
            frames: the stack of frames to predict Q values from

        Returns:
            a tuple of:
                - the optimal action
                - the Q value for the optimal action

        """
        # predict the values of each action
        actions = self.model.predict(
            frames.reshape(self.input_shape),
            batch_size=1
        )
        # draw a number in [0, 1] and explore if it's less than the
        # exploration rate
        if np.random.random() < self.exploration_rate:
            # select a random action. the output shape of the network implies
            # the action name by index, so use that shape as the upper bound
            optimal_action = np.random.randint(0, self.num_actions)
        else:
            # select the action with the highest estimated score as the
            # optimal action
            optimal_action = np.argmax(actions)

        # return the optimal action and its corresponding Q value
        return optimal_action, actions[0, optimal_action]

    def _train(self,
        s: np.ndarray,
        a: np.ndarray,
        r: np.ndarray,
        d: np.ndarray,
        s2: np.ndarray
    ) -> float:
        """
        Train the network on a mini-batch of replay data.

        Notes:
            all arguments are arrays that should be of the same size

        Args:
            s: an array of current states
            a: an array of actions
            r: an array of rewards
            d: an array of terminal flags
            s2: an array of next states

        Returns:
            the loss as a result of the training

        """
        # initialize y values as zeros
        y = np.zeros((s.shape[0], self.num_actions))

        # iterate over the samples in this mini-batch
        for index in range(len(s)):
            # get the Q values for this state
            y[index] = self.model.predict(
                s[index].reshape(self.input_shape),
                batch_size=1
            )
            # get the Q values for the next state
            a_prime = self.model.predict(
                s2[index].reshape(self.input_shape),
                batch_size=1
            )
            # calculate target y values
            # y = r_j for terminal phi_{j+1}
            y[index, a[index]] = r[index]
            # check if y is terminal, if so y = t_j + gamma * max_{a'} Q
            if not d[index]:
                y[index, a[index]] += self.discount_factor * np.max(a_prime)

        return self.model.train_on_batch(s, y)

    def _initial_state(self) -> np.ndarray:
        """Reset the environment and return the initial state."""
        # reset the environment, duplicate the initial state based on the
        # number of frames per action
        return np.stack(
            [self._downsample(self.env.reset())] * self.frames_per_action,
            axis=2
        )

    def _next_state(self, action: int) -> tuple:
        """
        Return the next state based on the given action.

        Args:
            action: the action to perform for some frames

        Returns:
            a tuple of:
                - the next state
                - the average reward over the frames
                - the done flag

        """
        # create buffers to store results in over the frame range
        next_state = []
        reward = 0
        # iterate over the number of buffered frames
        for _ in range(self.frames_per_action):
            # render the frame
            self.env.render()
            # make the step and observe the state, reward, done
            _next_state, _reward, done, _ = self.env.step(action=action)
            # store the state and reward from this frame
            next_state.append(self._downsample(_next_state))
            # TODO: is this necessary?
            _reward = _reward if not done else -10
            # add the current reward to the total reward
            reward += _reward

        # convert the state to an ndarray with the expected size
        next_state = np.stack(next_state, axis=2)

        # return the next state, the average reward and the done flag
        return next_state, reward, done

    def train(self,
        episodes: int=1000,
        batch_size: int=32,
        callback: Callable=None
    ) -> None:
        """
        Train the network for a number of episodes (games).

        Args:
            episodes: the number of episodes (games) to play
            batch_size: the size of the replay history batches

        Returns:
            None

        """
        for episode in tqdm(range(episodes), unit='episode'):
            # reset the game and get the initial state
            state = self._initial_state()
            # the done flag indicating that an episode has ended
            done = False
            score = 0
            loss = 0
            # loop until done
            while not done:
                # predict the best action based on the current state
                action, Q = self.predict_action(state)
                # hold the action for the number of frames
                next_state, reward, done = self._next_state(action)
                score += reward
                # push the memory onto the replay queue
                self.queue.push(state, action, reward, done, next_state)
                # set the state to the new state
                state = next_state
                # train the network on replay memory
                loss += self._train(*self.queue.sample(size=batch_size))
                # decay the exploration rate
                self.exploration_rate = self.exploration_rate * self.exploration_decay

            # pass the score to the callback at the end of the episode
            if callable(callback):
                callback(score)

    def run(self, games: int=30) -> np.ndarray:
        """
        Run the agent without training for a number of games.

        Args:
            games: the number of games to play

        Returns:
            an array of scores

        """
        # a list to keep track of the scores
        scores = np.zeros(games)
        # iterate over the number of games
        for game in tqdm(range(games), unit='game'):
            # reset the game and get the initial state
            state = self._initial_state()
            # the done flag indicating that a game has ended
            done = False
            score = 0
            # loop until done
            while not done:
                # predict the best action based on the current state
                action, Q = self.predict_action(state)
                # hold the action for the number of frames
                next_state, reward, done = self._next_state(action)
                score += reward
                # set the state to the new state
                state = next_state
            # push the score onto the history
            scores[game] = score

        return scores


# explicitly define the outward facing API of this module
__all__ = ['DeepQAgent']
