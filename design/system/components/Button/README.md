# Button

Raised pill for actions; primary for the one action a view is for, secondary for the rest.

Provide `children` (a verb that says what happens: "Start audit of 12 samples", never "Submit"), `variant` (`primary` or `secondary`, the default), `onClick` or `type`, and `disabled`.

- The outline is a bezel: lit by `color-bezel-hi` on top, shaded by `color-bezel-lo` below, over a face that is lighter on top. Primary mixes its bezel from `color-accent`.
- Hovering brightens the bezel toward `color-sheen`. Pressing flips bezel and face and sinks the button into `shadow-inset`, the one place the motif answers a hand.
- One primary per view. Keep labels in sentence case.
- Don't put icons alone in a button; the label carries the meaning.
