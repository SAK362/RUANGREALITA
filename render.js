// Pakai: node render.js jobs/0001/job.json out/0001.mp4 [--workers 4] [--fps 30] [--w 1080] [--h 1920]
const fs=require('fs'),path=require('path'),cp=require('child_process');
let pw;try{pw=require('playwright')}catch(e){pw=require('/opt/npm-tools/node_modules/playwright')}
const arg=(k,d)=>{const i=process.argv.indexOf('--'+k);return i>0?process.argv[i+1]:d};
const jobPath=process.argv[2],outPath=process.argv[3]||'out/video.mp4';
const WORKERS=+arg('workers',2),FPS=+arg('fps',30),W=+arg('w',1080),H=+arg('h',1920);
const CHROME=process.env.CHROME_PATH||undefined;
const job=JSON.parse(fs.readFileSync(jobPath,'utf8'));const dir=path.dirname(jobPath);
const sprites=JSON.parse(fs.readFileSync(path.join(__dirname,'sprites/meta.json'),'utf8'));
const probe=f=>parseFloat(cp.execSync(`ffprobe -v error -show_entries format=duration -of csv=p=0 "${f}"`).toString());
// durasi tiap beat dari audio TTS (audio/beat_00.wav ...), fallback estimasi
job.beats.forEach((b,i)=>{const nm=`beat_${String(i).padStart(2,'0')}`;const f=['wav','opus','mp3','ogg'].map(x=>path.join(dir,'audio',nm+'.'+x)).find(fs.existsSync);b.audio=f||null;b.dur=b.audio?probe(f):Math.max(1,b.text.split(/\s+/).length*.38)});
// words.json (hasil Whisper): {"beats":[[[mulai,akhir],...per kata],...]} relatif ke awal audio beat
const wj=path.join(dir,'words.json');if(fs.existsSync(wj)){const W=JSON.parse(fs.readFileSync(wj,'utf8')).beats||[];job.beats.forEach((b,i)=>{if(W[i])b.wt=W[i]});console.log('words.json dipakai:',W.length,'beat')}
job.beats[job.beats.length-1].punch=true;
const NEED=[...new Set([...job.cast,...(job.extras||[])])];for(const n of NEED)if(!sprites[n])throw new Error('Sprite tidak ada untuk karakter: '+n);
async function open(){const b=await pw.chromium.launch({executablePath:CHROME,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--enable-webgl']});
 const p=await b.newPage({viewport:{width:W,height:H}});p.on('pageerror',e=>console.log('pageerror:',e.message.slice(0,400)));
 await p.addInitScript(`window.RW=${W};window.RH=${H};window.JOB=${JSON.stringify(job)};window.SMETA=${JSON.stringify(sprites)}`);
 await p.goto('file://'+path.join(__dirname,'engine/engine.html'));await p.waitForFunction('window.READY',null,{timeout:90000});await p.evaluate(()=>document.fonts.load('700 40px Poppins'));
 for(const n of NEED){const uri='data:image/png;base64,'+fs.readFileSync(path.join(__dirname,'sprites',n+'.png')).toString('base64');await p.evaluate(([n,u])=>window.addSprite(n,u),[n,uri])
 const fd=path.join(__dirname,'sprites/faces');if(job.cast.includes(n)&&fs.existsSync(fd))for(const f of fs.readdirSync(fd))if(f.startsWith(n+'__')){const v=f.slice(n.length+2,-4);const u2='data:image/png;base64,'+fs.readFileSync(path.join(fd,f)).toString('base64');await p.evaluate(([n,u,v])=>window.addSprite(n,u,v),[n,u2,v])}}
 await p.evaluate(()=>window.initExtras());return{b,p}}
(async()=>{const first=await open();const total=await first.p.evaluate(()=>window.TOTAL);const N=Math.ceil(total*FPS);console.log(`durasi ${total.toFixed(1)}s, ${N} frame, ${WORKERS} worker`);
 const fr=path.join('out','frames_'+(job.id||'x'));if(!process.argv.includes('--reuse')){fs.rmSync(fr,{recursive:true,force:true})}fs.mkdirSync(fr,{recursive:true});
 const sess=[first];for(let k=1;k<WORKERS;k++)sess.push(await open());
 let next=0;const t0=Date.now();
 await Promise.all(sess.map(async s=>{for(;;){const i=next++;if(i>=N)break;const d=await s.p.evaluate(t=>window.renderFrame(t),i/FPS);fs.writeFileSync(path.join(fr,`f${String(i).padStart(5,'0')}.jpg`),Buffer.from(d.split(',')[1],'base64'));if(i%60===0)console.log(`frame ${i}/${N} (${((Date.now()-t0)/1000).toFixed(0)}s)`)}}));
 await Promise.all(sess.map(s=>s.b.close()));
 // audio: tempel tiap beat pada waktu mulainya (sama dengan engine: LEAD .5s, GAP .28s)
 let cur=.5;const inputs=[],filt=[],labs=[];job.beats.forEach((b,i)=>{if(b.audio){const k=inputs.length/2;inputs.push('-i',b.audio);filt.push(`[${k+1}:a]adelay=${Math.round(cur*1000)}:all=1[a${i}]`);labs.push(`[a${i}]`)}cur+=b.dur+.28});
 fs.mkdirSync(path.dirname(outPath),{recursive:true});
 const vin=['-framerate',String(FPS),'-i',path.join(fr,'f%05d.jpg')];
 let args;if(inputs.length){
  args=['-y',...vin,...inputs,'-filter_complex',filt.join(';')+`;${labs.join('')}amix=inputs=${filt.length}:normalize=0:duration=longest[aout]`,'-map','0:v','-map','[aout]','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',String(total),outPath]}
 else args=['-y',...vin,'-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p',outPath];
 cp.execFileSync('ffmpeg',args,{stdio:'inherit'});fs.rmSync(fr,{recursive:true,force:true});console.log('selesai',outPath)})().catch(e=>{console.error('ERR',e);process.exit(1)});
