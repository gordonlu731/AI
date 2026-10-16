// Initial settings only. These values are fixed before collecting any outcomes.
// No reference to stage flags, elapsed time, velocities or answer labels.
export const PROTOCOL_ID='BW-PREDICT-002';
export const HORIZON=30;
export const REPEATS=3;
export const CONTACTS=['barrier','gate','wheel','lever','bucket','hammer'];
export const REFERENCE={id:'REF',label:'Reference / 原始配置',ballDensity:24,removeDominoOrdinal:null,barrier:null};
export const CASES=[
 {id:'Y1',label:'Lower barrier / 降低挡板',ballDensity:24,removeDominoOrdinal:null,barrier:{x:-7.9,zOffset:0,height:.30,width:2.4,thickness:.26,bottomRelativeToTrack:-.15}},
 {id:'Y2',label:'Narrow offset barrier / 缩窄并偏移挡板',ballDensity:24,removeDominoOrdinal:null,barrier:{x:-7.9,zOffset:.65,height:1.5,width:.60,thickness:.26,bottomRelativeToTrack:-.15}},
 {id:'Y3',label:'Remove domino 04 / 移除中间骨牌',ballDensity:24,removeDominoOrdinal:4,barrier:null},
 {id:'Y4',label:'Lower ball density / 降低首球密度',ballDensity:2.4,removeDominoOrdinal:null,barrier:null},
];
for(const c of [REFERENCE,...CASES]){if(c.barrier)Object.freeze(c.barrier);Object.freeze(c);}Object.freeze(CASES);
export function getConfiguration(id){const c=[REFERENCE,...CASES].find(c=>c.id===id);if(!c)throw Error(`Unknown experiment: ${id}`);return c;}
