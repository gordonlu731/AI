// Case definitions contain initial settings only, never outcome labels.
export const PROTOCOL_ID='BW-PREDICT-001';
export const CONTACTS=['barrier','gate','wheel','lever','bucket','hammer'];
export const CASES=[
  {id:'X1',options:{removeDomino:false,addObstacle:true}},
  {id:'X2',options:{removeDomino:false,addObstacle:false}},
  {id:'X3',options:{removeDomino:true,addObstacle:false}},
  {id:'X4',options:{removeDomino:true,addObstacle:true}},
];
export const HORIZON=30;
export const REPEATS=3;
