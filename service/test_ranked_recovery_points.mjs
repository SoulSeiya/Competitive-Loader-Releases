import assert from 'node:assert/strict';
import {settleRanked} from './ranked.mjs';
function fixture(attempt=1,recovery_enabled=true){return {s:{players:{a:{rating:1000,played:0,wins:0,losses:0,abandons:0,fairplay_points:7},b:{rating:1000,played:0,wins:0,losses:0,abandons:0,fairplay_points:4}}},m:{players:['a','b'],attempt,recovery_enabled}};}
let {s,m}=fixture();settleRanked(s,m,'a','resultado',100);
assert.equal(s.players.b.rating,1006,'A completed desync rematch must add six ranked points without subtracting Elo');
assert.equal(m.delta.b,6);assert.equal(s.players.b.fairplay_points,4,'Do not add the superseded +3 separate bonus');
assert.equal(s.players.a.rating,1012);assert.equal(s.players.a.fairplay_points,17);
assert.equal(m.fairplay_delta.a,10);assert.equal(m.fairplay_delta.b,0);
assert.equal(s.players.b.losses,1);assert.equal(s.players.b.played,1);
settleRanked(s,m,'a','resultado',101);assert.equal(s.players.b.rating,1006);assert.equal(s.players.a.fairplay_points,17);
for(const reason of ['abandono','desconexion','cierre del juego']){
 ({s,m}=fixture());settleRanked(s,m,'a',reason,100);assert.equal(s.players.b.rating,988);assert.equal(s.players.b.fairplay_points,4);assert.equal(s.players.b.abandons,1);
}
for(const [attempt,enabled]of [[0,true],[1,false]]){
 ({s,m}=fixture(attempt,enabled));settleRanked(s,m,'a','resultado',100);assert.equal(s.players.b.rating,988);assert.equal(s.players.a.fairplay_points,7);
}
({s,m}=fixture());settleRanked(s,m,null,'revancha por desync caducada',100);assert.equal(s.players.b.rating,1000);assert.deepEqual(m.delta,{});
console.log('PASS: rematch loser +6 ranked, no Elo loss, winner unchanged, exact once, no protection for forfeit/timeout/ordinary sets');
