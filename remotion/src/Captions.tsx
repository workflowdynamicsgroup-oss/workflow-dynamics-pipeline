import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {CaptionWord} from './types';

// Word-timed captions: 7 words per group in 16:9, 4 in 9:16.
// The word being spoken is highlighted in electric blue.
export const Captions: React.FC<{words: CaptionWord[]; vertical: boolean}> = ({words, vertical}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = (frame / fps) * 1000;
  let current = -1;
  for (let i = 0; i < words.length; i++) {
    if (words[i].startMs <= t) current = i;
    else break;
  }
  if (current < 0) return null;
  const perGroup = vertical ? 4 : 7;
  const groupStart = Math.floor(current / perGroup) * perGroup;
  const group = words.slice(groupStart, groupStart + perGroup);

  const base: React.CSSProperties = {
    position: 'absolute',
    fontFamily: 'Arial Black, Arial, sans-serif',
    fontWeight: 900,
    color: '#fff',
    textShadow: '0 0 6px rgba(11,31,58,0.95), 0 2px 4px rgba(11,31,58,0.95), 2px 2px 0 rgba(11,31,58,0.9), -2px -2px 0 rgba(11,31,58,0.9), 2px -2px 0 rgba(11,31,58,0.9), -2px 2px 0 rgba(11,31,58,0.9)',
    textTransform: 'uppercase',
    lineHeight: 1.1,
  };
  const style: React.CSSProperties = vertical
    ? {...base, left: 65, right: 65, top: 640, fontSize: 66, textAlign: 'center'}
    : {...base, left: 464, right: 80, bottom: 70, fontSize: 54};

  return (
    <div style={style}>
      {group.map((w, i) => (
        <React.Fragment key={`${groupStart + i}`}>
          <span style={{color: groupStart + i === current ? '#1E6BFF' : '#fff'}}>{w.word}</span>{' '}
        </React.Fragment>
      ))}
    </div>
  );
};
