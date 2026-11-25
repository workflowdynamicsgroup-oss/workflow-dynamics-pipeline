import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {StatProps} from './types';

const BG = '#F4F7FB';
const INK = '#0B1F3A';
const BLUE = '#1E6BFF';

export const StatCard: React.FC<{stat: StatProps}> = ({stat}) => (
  <AbsoluteFill style={{backgroundColor: BG, color: INK, fontFamily: 'Arial, sans-serif', justifyContent: 'center', alignItems: 'center', padding: 80, textAlign: 'center'}}>
    <div style={{fontSize: 160, fontWeight: 900, color: BLUE}}>{stat.value}</div>
    <div style={{fontSize: 52, marginTop: 20}}>{stat.label}</div>
    <div style={{fontSize: 26, marginTop: 40, opacity: 0.7}}>{stat.source}</div>
  </AbsoluteFill>
);

// Side-by-side card: product A on the left, B on the right, one row revealed at a time.
export const CompareCard: React.FC<{stat: StatProps; vertical: boolean}> = ({stat, vertical}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const c = stat.compare!;
  const rows = c.rows;
  const rowStyle = (i: number): React.CSSProperties => {
    const start = (i / rows.length) * durationInFrames * 0.6;
    const opacity = interpolate(frame, [start, start + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    return {opacity, display: 'flex', flexDirection: vertical ? 'column' : 'row', borderBottom: '2px solid #C9D3E3', padding: vertical ? '18px 0' : '22px 0'};
  };
  return (
    <AbsoluteFill style={{backgroundColor: BG, color: INK, fontFamily: 'Arial, sans-serif', padding: vertical ? 60 : 120, justifyContent: 'center'}}>
      <div style={{display: 'flex', flexDirection: vertical ? 'column' : 'row', fontSize: vertical ? 36 : 40, fontWeight: 900, marginBottom: 30}}>
        {!vertical && <div style={{flex: c.kind === 'pain_points' ? 1.5 : 1, paddingRight: c.kind === 'pain_points' ? 24 : 0}} />}
        <div style={{flex: 1, color: BLUE}}>{c.a}</div>
        <div style={{flex: 1}}>{c.b}</div>
      </div>
      {rows.map((r, i) => (
        <div key={i} style={rowStyle(i)}>
          {c.kind === 'pain_points' ? (
            <div style={{flex: 1.5, fontSize: vertical ? 30 : 34, fontStyle: 'italic', opacity: 0.9, paddingRight: 24}}>{'\u201C' + r.label + '\u201D'}</div>
          ) : c.kind === 'pros_cons' ? (
            <div style={{flex: 1, fontSize: vertical ? 30 : 34, fontWeight: 900, color: r.label.toLowerCase().startsWith('con') ? '#D6336C' : BLUE}}>{r.label}</div>
          ) : (
            <div style={{flex: 1, fontSize: vertical ? 30 : 34, opacity: 0.8}}>{r.label}</div>
          )}
          <div style={{flex: 1, fontSize: vertical ? 38 : 40, fontWeight: 700, color: BLUE}}>{r.a}</div>
          <div style={{flex: 1, fontSize: vertical ? 38 : 40, fontWeight: 700}}>{r.b}</div>
        </div>
      ))}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: vertical ? 300 : 240, textAlign: 'center', fontSize: 24, opacity: 0.7}}>{stat.source}</div>
    </AbsoluteFill>
  );
};
