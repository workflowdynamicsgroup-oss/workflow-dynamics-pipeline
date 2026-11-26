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
// 16:9 uses a three-column grid with a real gap, so the two product columns never touch, and the card keeps
// clear of the caption band at the bottom (the source line is part of the card, not pinned over the rows).
export const CompareCard: React.FC<{stat: StatProps; vertical: boolean}> = ({stat, vertical}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const c = stat.compare!;
  const rows = c.rows;
  const fade = (i: number) => {
    const start = (i / rows.length) * durationInFrames * 0.6;
    return interpolate(frame, [start, start + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  };
  if (!vertical) {
    const pain = c.kind === 'pain_points';
    const cols = pain ? '1.35fr 1fr 1fr' : '0.8fr 1.1fr 1.1fr';
    const val = rows.length >= 4 ? 38 : rows.length === 3 ? 42 : 48;
    const lab = rows.length >= 4 ? 30 : 34;
    const grid: React.CSSProperties = {display: 'grid', gridTemplateColumns: cols, columnGap: 56, alignItems: 'center'};
    const cell: React.CSSProperties = {minWidth: 0, overflowWrap: 'break-word', lineHeight: 1.15};
    return (
      <AbsoluteFill style={{backgroundColor: BG, color: INK, fontFamily: 'Arial, sans-serif', padding: '60px 100px 250px', justifyContent: 'center'}}>
        <div style={{...grid, fontSize: 52, fontWeight: 900, marginBottom: 22}}>
          <div />
          <div style={{...cell, color: BLUE}}>{c.a}</div>
          <div style={cell}>{c.b}</div>
        </div>
        {rows.map((r, i) => (
          <div key={i} style={{...grid, opacity: fade(i), borderBottom: '2px solid #C9D3E3', padding: rows.length >= 4 ? '12px 0' : '18px 0'}}>
            {pain ? (
              <div style={{...cell, fontSize: lab, fontStyle: 'italic', opacity: 0.9}}>{'\u201C' + r.label + '\u201D'}</div>
            ) : c.kind === 'pros_cons' ? (
              <div style={{...cell, fontSize: lab, fontWeight: 900, color: r.label.toLowerCase().startsWith('con') ? '#D6336C' : BLUE}}>{r.label}</div>
            ) : (
              <div style={{...cell, fontSize: lab, opacity: 0.8}}>{r.label}</div>
            )}
            <div style={{...cell, fontSize: val, fontWeight: 700, color: BLUE}}>{r.a}</div>
            <div style={{...cell, fontSize: val, fontWeight: 700}}>{r.b}</div>
          </div>
        ))}
        <div style={{marginTop: 24, textAlign: 'center', fontSize: 26, opacity: 0.75}}>{stat.source}</div>
      </AbsoluteFill>
    );
  }
  const rowStyle = (i: number): React.CSSProperties => ({
    opacity: fade(i), display: 'flex', flexDirection: 'column', borderBottom: '2px solid #C9D3E3', padding: '18px 0',
  });
  return (
    <AbsoluteFill style={{backgroundColor: BG, color: INK, fontFamily: 'Arial, sans-serif', padding: 60, justifyContent: 'center'}}>
      <div style={{display: 'flex', flexDirection: 'column', fontSize: 36, fontWeight: 900, marginBottom: 30}}>
        <div style={{flex: 1, color: BLUE}}>{c.a}</div>
        <div style={{flex: 1}}>{c.b}</div>
      </div>
      {rows.map((r, i) => (
        <div key={i} style={rowStyle(i)}>
          {c.kind === 'pain_points' ? (
            <div style={{flex: 1.5, fontSize: 30, fontStyle: 'italic', opacity: 0.9, paddingRight: 24}}>{'\u201C' + r.label + '\u201D'}</div>
          ) : c.kind === 'pros_cons' ? (
            <div style={{flex: 1, fontSize: 30, fontWeight: 900, color: r.label.toLowerCase().startsWith('con') ? '#D6336C' : BLUE}}>{r.label}</div>
          ) : (
            <div style={{flex: 1, fontSize: 30, opacity: 0.8}}>{r.label}</div>
          )}
          <div style={{flex: 1, fontSize: 38, fontWeight: 700, color: BLUE}}>{r.a}</div>
          <div style={{flex: 1, fontSize: 38, fontWeight: 700}}>{r.b}</div>
        </div>
      ))}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 300, textAlign: 'center', fontSize: 24, opacity: 0.7}}>{stat.source}</div>
    </AbsoluteFill>
  );
};
