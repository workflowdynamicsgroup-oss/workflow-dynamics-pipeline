import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';

// Ditto avatar, shown only inside the scripted avatar blocks.
// 16:9: 384x288, flush bottom, 40 px from the left.
// 9:16: 216x162, 40 px from the left, top edge at 380 px.
// The src is the VP9 alpha webm made by scripts/make_avatar_alpha.sh (matte merged into the Ditto video).
export const Avatar: React.FC<{src: string; vertical: boolean; offsetFrames?: number}> = ({src, vertical, offsetFrames}) => {
  const box: React.CSSProperties = vertical
    ? {position: 'absolute', left: 40, top: 380, width: 216, height: 162}
    : {position: 'absolute', left: 40, bottom: 0, width: 384, height: 288};
  return (
    <AbsoluteFill>
      <div style={box}>
        <OffthreadVideo src={staticFile(src)} transparent muted startFrom={offsetFrames ?? 0} style={{width: '100%', height: '100%'}} />
      </div>
    </AbsoluteFill>
  );
};
