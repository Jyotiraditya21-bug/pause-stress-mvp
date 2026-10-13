const analyticsDomain=import.meta.env.VITE_ANALYTICS_DOMAIN;

function scrubEvent(event){
  if(!event)return event;
  delete event.breadcrumbs;delete event.extra;delete event.contexts;
  if(event.request){delete event.request.data;delete event.request.cookies;delete event.request.headers;}
  return event;
}

export async function initializeMonitoring(){
  const dsn=import.meta.env.VITE_SENTRY_DSN;
  if(dsn){
    const Sentry=await import('@sentry/react');
    Sentry.init({dsn,beforeBreadcrumb:()=>null,beforeSend:scrubEvent,sendDefaultPii:false});
  }
  if(analyticsDomain){
    const script=document.createElement('script');script.defer=true;script.dataset.domain=analyticsDomain;script.src='https://plausible.io/js/script.js';document.head.appendChild(script);
  }
}

export function trackEvent(name,props={}){
  if(!analyticsDomain)return;
  const allowed=name==='scan_started'?{}:{status:String(props.status||''),reason:String(props.reason||'').slice(0,80)};
  globalThis.plausible?.(name,{props:allowed});
}
