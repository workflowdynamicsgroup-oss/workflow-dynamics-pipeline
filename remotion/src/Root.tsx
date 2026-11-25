import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {Main} from './Main';
import {VideoProps} from './types';

const emptyProps: VideoProps = {
  format: '16x9',
  fps: 25,
  durationSec: 10,
  shots: [],
  captions: [],
  disclosure: '',
  disclosureWindowsSec: [],
  cornerTag: '',
};

// Size, frame rate and length come from the props file, so one composition
// renders whichever format the props describe.
const sizeFor = (props: VideoProps) =>
  props.format === '9x16' ? {width: 1080, height: 1920} : {width: 1920, height: 1080};

const calc: CalculateMetadataFunction<VideoProps> = ({props}) => ({
  ...sizeFor(props),
  fps: props.fps,
  durationInFrames: Math.round(props.durationSec * props.fps),
});

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Long16x9"
      component={Main}
      defaultProps={{...emptyProps, format: '16x9'}}
      calculateMetadata={calc}
      width={1920}
      height={1080}
      fps={25}
      durationInFrames={250}
    />
    <Composition
      id="Short9x16"
      component={Main}
      defaultProps={{...emptyProps, format: '9x16'}}
      calculateMetadata={calc}
      width={1080}
      height={1920}
      fps={25}
      durationInFrames={250}
    />
  </>
);
