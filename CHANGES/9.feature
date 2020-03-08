Improved the way ``linecache`` is used: now the number of files to be put
into the ``linecache`` is limited to 100. The eviction is done by implementing
recently used strategy.
