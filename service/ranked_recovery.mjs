// Opt-in ranked recovery; legacy clients keep the existing no-points void.
export function checkpointScore(m,id,score){
 if(!m.recovery_enabled||!Array.isArray(score)||score.length!==2||!score.every(v=>Number.isInteger(v)&&v>=0&&v<2))return;
 const base=m.checkpoint||[0,0],previous=m.score_reports?.[id]||base;
 if(score.some((v,i)=>v<base[i]||v<previous[i]))return;
 m.score_reports??={};m.score_reports[id]=score.slice();
 const [a,b]=m.players.map(p=>m.score_reports[p]);
 if(a&&b&&a.every((v,i)=>v===b[i]))m.checkpoint=a.slice();
}
export function desyncProof(p){
 return p&&Number.isInteger(p.blank)&&p.blank>=0&&p.blank<=2147483647&&
  /^[a-f0-9]{16}$/.test(p.local_hash||'')&&/^[a-f0-9]{16}$/.test(p.peer_hash||'')&&p.local_hash!==p.peer_hash?
  {blank:p.blank,local_hash:p.local_hash,peer_hash:p.peer_hash}:null;
}
export function pairedDesync(m){
 const [a,b]=m.players.map(id=>desyncProof(m.desync_proofs?.[id]));
 return !!(a&&b&&a.blank===b.blank&&a.local_hash===b.peer_hash&&a.peer_hash===b.local_hash);
}
export function openRecovery(m,now){
 if(!m.recovery_enabled||!pairedDesync(m)||m.phase!=='playing'||(m.attempt||0)>=3)return false;
 m.phase='recovering';m.recovery={score:(m.checkpoint||[0,0]).slice(),votes:{},expires:now+120000};
 return true;
}
export function waitingProofs(m,now){
 if(!m.recovery_enabled||!m.players.every(id=>m.faults?.[id])||m.players.every(id=>desyncProof(m.desync_proofs?.[id])))return false;
 m.proof_deadline??=now+45000;
 return now<m.proof_deadline;
}
export function recoveryView(m,id){
 if(m.finished||m.phase!=='recovering'||!m.recovery)return null;
 return {score:m.recovery.score,expires:m.recovery.expires,accepted:!!m.recovery.votes[id],
  confirmations:m.players.filter(p=>m.recovery.votes[p]).length,attempt:m.attempt||0};
}
