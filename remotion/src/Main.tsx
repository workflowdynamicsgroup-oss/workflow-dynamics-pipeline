import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {ShotProps, VideoProps} from './types';
import {Captions} from './Captions';
import {CompareCard, StatCard} from './Compare';
import {Avatar} from './Avatar';

const toFrame = (sec: number, fps: number) => Math.round(sec * fps);

// Slow push-in on stills (the direction is a fixed zoom-in for now).
const Still: React.FC<{src: string}> = ({src}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [1, 1.08], {
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <Img
        src={staticFile(src)}
        style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${scale})`}}
      />
    </AbsoluteFill>
  );
};

const Shot: React.FC<{shot: ShotProps; format: string}> = ({shot, format}) => {
  switch (shot.kind) {
    case 'wan':
    case 'broll':
      return (
        <AbsoluteFill>
          <OffthreadVideo src={staticFile(shot.src)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </AbsoluteFill>
      );
    case 'still':
      return <Still src={shot.src} />;
    case 'picture':
      return (
        <AbsoluteFill>
          <Img src={staticFile(shot.src)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
        </AbsoluteFill>
      );
    case 'screen':
    case 'clip':
      return (
        <AbsoluteFill>
          <OffthreadVideo src={staticFile(shot.src)} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
        </AbsoluteFill>
      );
    case 'stat':
      if (shot.stat?.compare) {
        return <CompareCard stat={shot.stat} vertical={format === '9x16'} />;
      }
      return shot.stat ? <StatCard stat={shot.stat} /> : null;
    default:
      return null;
  }
};

export const Main: React.FC<VideoProps> = (p) => {
  const {fps} = useVideoConfig();
  const vertical = p.format === '9x16';
  const disclosureFrames = p.disclosureWindowsSec.map(([a, b]) => [toFrame(a, fps), toFrame(b, fps)]);
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      {p.narrationSrc ? <Audio src={staticFile(p.narrationSrc)} /> : null}

      {p.shots.map((s) => {
        const from = toFrame(s.startSec, fps);
        const to = toFrame(s.endSec, fps);
        return (
          <Sequence key={s.id} from={from} durationInFrames={Math.max(1, to - from)}>
            <Shot shot={s} format={p.format} />
          </Sequence>
        );
      })}

      {(p.avatarBlocks ?? []).map((b, i) => {
        const from = toFrame(b.startSec, fps);
        const to = toFrame(b.endSec, fps);
        return (
          <Sequence key={`avatar-${i}`} from={from} durationInFrames={Math.max(1, to - from)}>
            <Avatar src={b.src} vertical={vertical} offsetFrames={toFrame(b.offsetSec ?? 0, fps)} />
          </Sequence>
        );
      })}

      <Captions words={p.captions} vertical={vertical} />

      <DisclosureLayer
        text={p.disclosure}
        windows={disclosureFrames}
        vertical={vertical}
      />

      <div
        style={{
          position: 'absolute',
          right: vertical ? 40 : 30,
          top: vertical ? 1180 : 30,
          opacity: 0.55,
          color: '#fff',
          background: 'rgba(11,31,58,0.7)',
          padding: '4px 12px',
          borderRadius: 6,
          fontFamily: 'Arial, sans-serif',
          fontSize: vertical ? 26 : 20,
        }}
      >
        {p.cornerTag}
      </div>
    </AbsoluteFill>
  );
};

// On-screen disclosure only (R-DISC): never in the narration or captions.
const DisclosureLayer: React.FC<{text: string; windows: number[][]; vertical: boolean}> = ({
  text,
  windows,
  vertical,
}) => {
  const frame = useCurrentFrame();
  const visible = windows.some(([a, b]) => frame >= a && frame < b);
  if (!visible || !text) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: vertical ? 700 : 140,
        textAlign: 'center',
        color: '#fff',
        fontFamily: 'Arial, sans-serif',
        fontSize: vertical ? 34 : 30,
      }}
    >
      <span style={{background: 'rgba(11,31,58,0.75)', padding: '6px 20px', borderRadius: 8, textShadow: 'none'}}>{text}</span>
    </div>
  );
};
