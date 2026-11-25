// Mirrors the props written by props/build_props.py, plus the optional fields
// the composition needs (narrationSrc, avatarBlocks, compare rows).
export type ShotKind = 'wan' | 'still' | 'broll' | 'stat' | 'screen' | 'clip' | 'picture';

export type CompareRow = {label: string; a: string; b: string};

export type Compare = {
  kind: string;
  a: string;
  b: string;
  rows: CompareRow[];
};

export type StatProps = {
  value: string;
  label: string;
  source: string;
  compare?: Compare;
};

export type ShotProps = {
  id: string;
  startSec: number;
  endSec: number;
  kind: ShotKind;
  src: string;
  stat?: StatProps;
};

export type CaptionWord = {word: string; startMs: number; endMs: number};

export type AvatarBlock = {src: string; startSec: number; endSec: number};

export type VideoProps = {
  format: '16x9' | '9x16';
  fps: number;
  durationSec: number;
  shots: ShotProps[];
  captions: CaptionWord[];
  disclosure: string;
  disclosureWindowsSec: [number, number][];
  cornerTag: string;
  narrationSrc?: string;
  avatarBlocks?: AvatarBlock[];
};
