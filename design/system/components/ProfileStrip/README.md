# ProfileStrip

One cell per label: the observed intensity fills a channel, with the expected band lit faintly behind. Markers: ✓ expected and found, – expected but missing, ! expected absent but found, ⚑ judges differ by two points or more.

Provide `cells` (`{label, family, observed, expected: {kind: 'present' | 'absent' | 'either', min?, max?}, disputed?}`) and optionally `label`.
