import { useEffect, useRef, useState } from 'react';
import { liveUrl, useLiveCameras, type LiveFeed } from '../../api/devices';

const time = (iso: string) => new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

/** The kiosk camera, live at full quality, relayed by the API. Nothing is recorded. */
export function KioskLive() {
  const feeds = useLiveCameras();
  if (feeds.error) return <p role="alert" className="text-crit">{feeds.error.message}</p>;
  const list = feeds.data ?? [];
  if (!list.length) return <Frame title="Kiosk camera" status={feeds.isPending ? 'Connecting…' : undefined} offline={!feeds.isPending} />;
  return <>{list.map((f) => <Feed key={f.device_id} f={f} />)}</>;
}

function Feed({ f }: { f: LiveFeed }) {
  const [attempt, setAttempt] = useState(0);
  const [broken, setBroken] = useState(false);
  const wasLive = useRef(f.live);
  useEffect(() => {
    if (f.live && !wasLive.current) { setAttempt((a) => a + 1); setBroken(false); }  // the bridge came back: open a new stream
    wasLive.current = f.live;
  }, [f.live]);
  // The laptop only sends frames once someone watches, so the first second after opening has no fps yet.
  const status = !f.live ? undefined : f.fps > 0 ? `${Math.round(f.fps)} fps · ${f.w}×${f.h}` : 'Starting video…';
  return (
    <Frame title={`Kiosk camera · ${f.code}`} status={status} viewers={f.live ? f.viewers : undefined}
      offline={!f.live} lastLive={f.last_frame_at} det={f.live ? f.det : null}>
      {f.live && !broken && (
        <img src={liveUrl(f.device_id, attempt)} onError={() => setBroken(true)} className="size-full object-contain"
          alt={`Live view of the kiosk tray from ${f.code}, with the items the camera recognises outlined`} />
      )}
      {f.live && broken && (
        <div className="grid size-full place-items-center content-center gap-3 text-sm">
          <p>The video stopped.</p>
          <button className="rounded-lg bg-white/15 px-4 py-2 font-semibold hover:bg-white/25 focus-visible:outline-2 focus-visible:outline-white"
            onClick={() => { setAttempt((a) => a + 1); setBroken(false); }}>
            Reconnect
          </button>
        </div>
      )}
    </Frame>
  );
}

function Frame({ title, status, viewers, offline = false, lastLive, det, children }: {
  title: string; status?: string; viewers?: number; offline?: boolean; lastLive?: string | null;
  det?: LiveFeed['det']; children?: React.ReactNode;
}) {
  const box = useRef<HTMLElement>(null);
  const [full, setFull] = useState(false);
  useEffect(() => {
    const on = () => setFull(document.fullscreenElement === box.current);
    document.addEventListener('fullscreenchange', on);
    return () => document.removeEventListener('fullscreenchange', on);
  }, []);
  const live = !offline && !!status;
  return (
    <section ref={box} aria-label={title} className="flex flex-col overflow-hidden rounded-xl bg-[#14231c] text-white">
      <div className="flex min-h-10 items-center gap-3 bg-black/40 px-3 py-1.5 text-xs">
        <span className="flex items-center gap-1.5 font-bold tracking-wide">
          <span className={`size-2 rounded-full ${live ? 'bg-[#f04438] motion-safe:animate-pulse' : 'bg-white/40'}`} />
          {live ? 'LIVE' : 'OFFLINE'}
        </span>
        <span>{title}</span>
        <span className="ml-auto flex items-center gap-3 text-white/80" aria-live="polite">
          {status && <span className="tabular-nums">{status}</span>}
          {viewers !== undefined && <span>{viewers} watching</span>}
        </span>
        {live && (
          <button className="flex items-center gap-1.5 rounded-md px-2 py-1 font-semibold hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-white"
            onClick={() => (full ? document.exitFullscreen() : box.current?.requestFullscreen())}>
            <svg viewBox="0 0 24 24" className="size-4 fill-none stroke-current stroke-2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d={full ? 'M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3' : 'M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3'} />
            </svg>
            {full ? 'Exit full screen' : 'Full screen'}
          </button>
        )}
      </div>

      <div className={`relative bg-black ${full ? 'flex-1' : 'aspect-video'}`}>
        {children}
        {offline && (
          <div className="absolute inset-0 grid place-items-center content-center gap-1 px-6 text-center">
            <p className="text-base font-semibold">Kiosk camera offline</p>
            <p className="max-w-[46ch] text-sm text-white/75">
              The laptop bridge isn’t sending video. Start <code className="text-white">kiosk_bridge.py</code> with the kiosk’s SapulMRF key set.
            </p>
            {lastLive && <p className="mt-2 text-xs text-white/60">Last live {time(lastLive)}</p>}
          </div>
        )}
        {!offline && !status && <p className="absolute inset-0 grid place-items-center text-sm text-white/75">Connecting…</p>}
      </div>

      {det && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 bg-black/40 px-3 py-2 text-xs">
          <span className="rounded-md bg-leaf-700 px-2 py-0.5 font-bold">{det.category}</span>
          <span className="tabular-nums text-white/85">
            {det.recyclable} recyclable · {det.residual} residual · {det.bio} biodegradable
            {det.conf != null && ` · ${Math.round(det.conf * 100)}% sure`}
          </span>
          {!!det.progress && (
            <span className="ml-auto flex items-center gap-2 text-white/85">
              Holding steady
              <span className="h-1.5 w-28 overflow-hidden rounded-full bg-white/15" role="progressbar" aria-label="Holding steady"
                aria-valuenow={Math.round(det.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
                <span className="block h-full rounded-full bg-leaf-300 transition-[width] duration-200" style={{ width: `${Math.min(100, det.progress * 100)}%` }} />
              </span>
            </span>
          )}
        </div>
      )}
    </section>
  );
}
