// A cancelled or timed-out initialization must dispose of a late resource.
export function awaitResource(source,{isCurrent,dispose=()=>{},message,timeoutMs=30000}) {
  return new Promise((resolve,reject)=>{
    let settled=false;
    const timer=setTimeout(()=>{settled=true;reject(new Error(message));},timeoutMs);
    Promise.resolve(source).then(value=>{
      if(settled||!isCurrent()) {
        dispose(value);
        if(!settled){settled=true;clearTimeout(timer);const e=new Error('Initialization cancelled');e.name='AbortError';reject(e);}
        return;
      }
      settled=true;clearTimeout(timer);resolve(value);
    },error=>{if(!settled){settled=true;clearTimeout(timer);reject(error);}});
  });
}
