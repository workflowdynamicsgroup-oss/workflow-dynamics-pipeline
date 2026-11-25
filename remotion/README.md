# Remotion composition (long-form VS video)

Reads the props files that `props/build_props.py` writes (`props-16x9.json`,
`props-9x16.json`). Two compositions: `Long16x9` (1920x1080) and `Short9x16` (1080x1920).

## Install and check

    cd remotion
    npm install
    npm run typecheck

## Render a test slice (before any full render)

Put the package folder (clips/, stills/, assets/, broll/, avatar/, narration) in
`pkg/`, then render with the props for that format:

    npx remotion render src/index.ts Long16x9 out/test-20s.mp4 --props=props.json --public-dir=pkg --frames=0-499

## Open gaps (must close before the first full render)

1. `build_props.py` writes `fps: 30`; the rules (R-SPEC) say 25. Composition follows the props value, so fix the builder first.
2. `build_props.py` does not copy `compare` rows from the source file into `stat`, so comparison cards fall back to plain stat cards.
3. `build_props.py` writes one `avatarSrc`. The composition needs `avatarBlocks` (`{src, startSec, endSec}` per block) and `narrationSrc`.
4. Avatar alpha: the Ditto mp4 has no alpha. Merge the matte first, for example
   `ffmpeg -i block1.mp4 -i block1-alpha.mp4 -filter_complex "[1:v]format=gray[m];[0:v][m]alphamerge" -c:v qtrle avatar-block1.mov`,
   then check transparency plays back in OffthreadVideo in the 20-second test.
5. Captions need the real narration timing from `captions/make_captions.py`; the grouping logic is untested.
