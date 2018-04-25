DeepQAgent(
    env=<Monitor<FrameStackEnv<ClipRewardEnv<PenalizeDeathEnv<DownsampleEnv<RewardCacheEnv<ToDiscreteActionSpaceEnv<TimeLimit<SuperMarioBrosEnv<SuperMarioBros-1-1-v0>>>>>>>>>>,
    render_mode='rgb_array'
    replay_memory_size=750000,
    discount_factor=0.99,
    update_frequency=4,
    optimizer=<keras.optimizers.Adam object at 0x1144a7cc0>,
    exploration_rate=AnnealingVariable(initial_value=1.0, final_value=0.1, steps=1000000),
    loss=huber_loss,
    target_update_freq=10000,
    dueling_network=True
)
