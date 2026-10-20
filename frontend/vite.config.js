import {execFileSync} from 'node:child_process';
import {defineConfig} from 'vite';
import {VitePWA} from 'vite-plugin-pwa';

export default defineConfig({
  base:process.env.VITE_BASE||process.env.VITE_BASE_PATH||'/',
  server:{proxy:{'/api':'http://127.0.0.1:8000'}},
  esbuild:{jsx:'automatic'},
  plugins:[{name:'release-metadata',generateBundle(){let commit='local';try{commit=execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim();}catch{}this.emitFile({type:'asset',fileName:'release.json',source:JSON.stringify({commit,algorithm:'quick-2.0',policy:'capture-clock-1',experimental:true})});}},VitePWA({
    registerType:'autoUpdate',
    includeAssets:['favicon.svg','icons/*.png','mediapipe/**/*'],
    manifest:{name:'Pause',short_name:'Pause',description:'A private, experimental 10-second Calm index.',display:'standalone',start_url:'.',theme_color:'#f8faf6',background_color:'#f8faf6',icons:[
      {src:'icons/pause-192.png',sizes:'192x192',type:'image/png'},
      {src:'icons/pause-512.png',sizes:'512x512',type:'image/png'},
      {src:'icons/pause-maskable-512.png',sizes:'512x512',type:'image/png',purpose:'maskable'}
    ]},
    workbox:{globPatterns:['**/*.{js,css,html,svg,png,wasm,task,ttf}'],globIgnores:['**/onnx/**','**/*ort-wasm*.*','**/models/**'],maximumFileSizeToCacheInBytes:15*1024*1024,navigateFallback:'index.html'}
  })]
});
