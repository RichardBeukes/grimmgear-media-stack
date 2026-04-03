// GrimmGear Mediarr — Frontend Application
// One interface. Everything works from here.

const API = '/api';
const content = document.getElementById('content');
let currentPage = 'dashboard';

async function api(path) {
    try { const r = await fetch(API + path, {signal: AbortSignal.timeout(10000)}); return r.ok ? await r.json() : null; } catch { return null; }
}
async function apiPost(path, data) {
    try { const r = await fetch(API + path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(10000)}); return r.ok ? await r.json() : null; } catch { return null; }
}
async function apiDelete(path) {
    try { const r = await fetch(API + path, {method:'DELETE',signal:AbortSignal.timeout(10000)}); return r.ok ? await r.json() : null; } catch { return null; }
}
function fmtBytes(b) { if(!b)return '0 B'; const u=['B','KB','MB','GB','TB']; const i=Math.floor(Math.log(b)/Math.log(1024)); return (b/Math.pow(1024,i)).toFixed(1)+' '+u[i]; }
function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

function navigate(page) {
    currentPage = page;
    document.querySelectorAll('.nav-link').forEach(l => l.classList.toggle('active', l.dataset.page === page));
    ({dashboard:renderDashboard,movies:renderMovies,tv:renderTV,search:renderSearch,downloads:renderDownloads,indexers:renderIndexers,settings:renderSettings}[page]||renderDashboard)();
}

// ── Dashboard ──────────────────────────────────────────────
async function renderDashboard() {
    content.textContent = '';
    const [status,health,movies,series,downloads,speed] = await Promise.all([api('/system/status'),api('/system/health'),api('/movies'),api('/series'),api('/downloads'),api('/downloads/speed')]);
    const dlSpeed = speed ? (speed.dl_speed/1048576).toFixed(1) : '0';
    document.getElementById('dl-speed-mini').textContent = dlSpeed+' MB/s';

    const statsDiv = document.createElement('div'); statsDiv.className='stat-row';
    const mkStat = (label,value,sub,color,click) => {
        const c=document.createElement('div'); c.className='stat-card'; if(click)c.onclick=()=>navigate(click);
        const bar=document.createElement('div'); bar.className='accent-bar'; bar.style.background=color; c.appendChild(bar);
        const l=document.createElement('div'); l.className='stat-label'; l.textContent=label; c.appendChild(l);
        const v=document.createElement('div'); v.className='stat-value'; v.textContent=value; c.appendChild(v);
        const s=document.createElement('div'); s.className='stat-sub'; s.textContent=sub; c.appendChild(s);
        return c;
    };
    statsDiv.appendChild(mkStat('Movies', movies?movies.length:0, (movies?movies.filter(m=>m.has_file).length:0)+' on disk', 'var(--yellow)', 'movies'));
    statsDiv.appendChild(mkStat('TV Series', series?series.length:0, '', 'var(--cyan)', 'tv'));
    statsDiv.appendChild(mkStat('Downloads', dlSpeed+' MB/s', (downloads?downloads.total:0)+' active', 'var(--green)', 'downloads'));
    statsDiv.appendChild(mkStat('System', health?health.status:'?', 'DB: '+(health?.checks?.database||'?'), health?.status==='healthy'?'var(--green)':'var(--red)', 'settings'));
    content.appendChild(statsDiv);

    // Downloads panel
    const dlPanel = document.createElement('div'); dlPanel.className='panel';
    const dlHead = document.createElement('div'); dlHead.className='panel-header'; dlHead.textContent='Active Downloads'; dlPanel.appendChild(dlHead);
    const dlBody = document.createElement('div'); dlBody.className='panel-body';
    if (downloads?.torrents?.length > 0) {
        downloads.torrents.slice(0,10).forEach(t => {
            const row = document.createElement('div'); row.className='table-row';
            const name = document.createElement('span'); name.style.cssText='flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'; name.textContent=t.name; row.appendChild(name);
            const pct = document.createElement('span'); pct.style.cssText='min-width:60px;text-align:right'; pct.textContent=(t.progress*100).toFixed(1)+'%'; row.appendChild(pct);
            const spd = document.createElement('span'); spd.style.cssText='min-width:70px;text-align:right;color:var(--green)'; spd.textContent=(t.dl_speed/1048576).toFixed(1)+' MB/s'; row.appendChild(spd);
            dlBody.appendChild(row);
        });
    } else { const e=document.createElement('div'); e.className='empty'; e.textContent='No active downloads'; dlBody.appendChild(e); }
    dlPanel.appendChild(dlBody); content.appendChild(dlPanel);
}

// ── Movies ─────────────────────────────────────────────────
async function renderMovies() {
    content.textContent = '';
    // Search bar
    const box = document.createElement('div'); box.className='search-box';
    const input = document.createElement('input'); input.className='search-input'; input.id='movie-search'; input.placeholder='Search TMDB for movies to add...';
    input.onkeydown = e => { if(e.key==='Enter')searchMovies(); };
    box.appendChild(input);
    const btn = document.createElement('button'); btn.className='btn btn-primary'; btn.textContent='Search'; btn.onclick=searchMovies; box.appendChild(btn);
    content.appendChild(box);
    const resultsDiv = document.createElement('div'); resultsDiv.id='movie-results'; content.appendChild(resultsDiv);
    // Library
    const panel = document.createElement('div'); panel.className='panel';
    const head = document.createElement('div'); head.className='panel-header'; head.textContent='My Movies'; panel.appendChild(head);
    const body = document.createElement('div'); body.className='panel-body';
    const grid = document.createElement('div'); grid.className='card-grid'; grid.id='movie-library';
    const movies = await api('/movies');
    if (movies?.length > 0) {
        head.textContent = 'My Movies ('+movies.length+')';
        movies.forEach(m => { const card=mkMediaCard(m.title,m.year,m.poster_url,m.has_file); grid.appendChild(card); });
    } else { const e=document.createElement('div'); e.className='empty'; e.textContent='No movies yet — search above to add'; grid.appendChild(e); }
    body.appendChild(grid); panel.appendChild(body); content.appendChild(panel);
}

function mkMediaCard(title,year,poster,hasFile) {
    const card = document.createElement('div'); card.className='media-card';
    const img = document.createElement('img'); img.src=poster||''; img.alt=title; img.onerror=function(){this.style.background='#333'}; card.appendChild(img);
    if(hasFile){ const badge=document.createElement('div'); badge.className='card-badge tag-green'; badge.textContent='ON DISK'; card.appendChild(badge); }
    const info = document.createElement('div'); info.className='card-info';
    const t = document.createElement('div'); t.className='card-title'; t.textContent=title; info.appendChild(t);
    const y = document.createElement('div'); y.className='card-year'; y.textContent=year||''; info.appendChild(y);
    card.appendChild(info); return card;
}

async function searchMovies() {
    const q = document.getElementById('movie-search').value; if(!q) return;
    const rd = document.getElementById('movie-results'); rd.textContent='Searching...';
    const data = await api('/search?q='+encodeURIComponent(q)+'&type=movie');
    rd.textContent='';
    if(!data?.length){ rd.textContent='No results. Set GG_TMDB_API_KEY env var for TMDB search.'; return; }
    const grid=document.createElement('div'); grid.className='card-grid';
    data.slice(0,20).forEach(m => {
        const card=mkMediaCard(m.title, (m.year||'')+(m.rating?' — ★'+m.rating.toFixed(1):''), m.poster_url, false);
        card.onclick=()=>addMovie(m.tmdb_id);
        grid.appendChild(card);
    });
    rd.appendChild(grid);
    const hint=document.createElement('div'); hint.style.cssText='padding:8px;color:var(--text-dim);font-size:12px'; hint.textContent='Click a movie to add it'; rd.appendChild(hint);
}
async function addMovie(id) { const r=await apiPost('/movies',{tmdb_id:id,monitored:true}); alert(r?.added?'Added: '+r.title:'Failed (exists or no TMDB key)'); if(r?.added)renderMovies(); }

// ── TV Shows ───────────────────────────────────────────────
async function renderTV() {
    content.textContent='';
    const box=document.createElement('div'); box.className='search-box';
    const input=document.createElement('input'); input.className='search-input'; input.id='tv-search'; input.placeholder='Search TMDB for TV shows...';
    input.onkeydown=e=>{if(e.key==='Enter')searchTV();}; box.appendChild(input);
    const btn=document.createElement('button'); btn.className='btn btn-primary'; btn.textContent='Search'; btn.onclick=searchTV; box.appendChild(btn);
    content.appendChild(box);
    const rd=document.createElement('div'); rd.id='tv-results'; content.appendChild(rd);
    const panel=document.createElement('div'); panel.className='panel';
    const head=document.createElement('div'); head.className='panel-header'; head.textContent='My Series'; panel.appendChild(head);
    const body=document.createElement('div'); body.className='panel-body';
    const grid=document.createElement('div'); grid.className='card-grid';
    const series=await api('/series');
    if(series?.length>0){ head.textContent='My Series ('+series.length+')'; series.forEach(s=>{grid.appendChild(mkMediaCard(s.title,s.year,s.poster_url,false));}); }
    else { const e=document.createElement('div'); e.className='empty'; e.textContent='No TV shows — search above'; grid.appendChild(e); }
    body.appendChild(grid); panel.appendChild(body); content.appendChild(panel);
}
async function searchTV() {
    const q=document.getElementById('tv-search').value; if(!q) return;
    const rd=document.getElementById('tv-results'); rd.textContent='Searching...';
    const data=await api('/search?q='+encodeURIComponent(q)+'&type=tv');
    rd.textContent='';
    if(!data?.length){rd.textContent='No results.'; return;}
    const grid=document.createElement('div'); grid.className='card-grid';
    data.slice(0,20).forEach(s=>{ const card=mkMediaCard(s.title,(s.year||'')+(s.rating?' — ★'+s.rating.toFixed(1):''),s.poster_url,false); card.onclick=()=>addSeries(s.tmdb_id); grid.appendChild(card); });
    rd.appendChild(grid);
}
async function addSeries(id) { const r=await apiPost('/series',{tmdb_id:id,monitored:true}); alert(r?.added?'Added: '+r.title+' ('+r.seasons+' seasons)':'Failed'); if(r?.added)renderTV(); }

// ── Search Indexers ────────────────────────────────────────
async function renderSearch() {
    content.textContent='';
    const box=document.createElement('div'); box.className='search-box';
    const input=document.createElement('input'); input.className='search-input'; input.id='idx-search'; input.placeholder='Search indexers (e.g. Inception 2010 1080p)...';
    input.onkeydown=e=>{if(e.key==='Enter')searchIndexers();}; box.appendChild(input);
    const btn=document.createElement('button'); btn.className='btn btn-primary'; btn.textContent='Search Indexers'; btn.onclick=searchIndexers; box.appendChild(btn);
    content.appendChild(box);
    const rd=document.createElement('div'); rd.id='idx-results'; content.appendChild(rd);
}
async function searchIndexers() {
    const q=document.getElementById('idx-search').value; if(!q) return;
    const rd=document.getElementById('idx-results'); rd.textContent='Searching indexers...';
    const data=await api('/search/indexers?q='+encodeURIComponent(q));
    rd.textContent='';
    if(!data?.results?.length){rd.textContent='No results from '+(data?.indexers_searched||0)+' indexers.'; return;}
    const panel=document.createElement('div'); panel.className='panel';
    const head=document.createElement('div'); head.className='panel-header'; head.textContent=data.total+' results from '+data.indexers_searched+' indexers'; panel.appendChild(head);
    const body=document.createElement('div'); body.className='panel-body';
    data.results.slice(0,50).forEach(r => {
        const row=document.createElement('div'); row.className='table-row';
        const dec=r.decision||{};
        // Status tag
        const tag=document.createElement('span'); tag.className='tag '+(dec.accepted?'tag-green':'tag-red'); tag.style.cssText='min-width:55px;text-align:center'; tag.textContent=dec.accepted?'OK':'BLOCKED'; row.appendChild(tag);
        // Quality
        const qual=document.createElement('span'); qual.className='tag tag-blue'; qual.style.cssText='min-width:50px;text-align:center'; qual.textContent=r.quality||'?'; row.appendChild(qual);
        // Seeders
        const seed=document.createElement('span'); seed.style.cssText='min-width:40px;text-align:right;color:var(--green)'; seed.textContent=r.seeders+'S'; row.appendChild(seed);
        // Size
        const size=document.createElement('span'); size.style.cssText='min-width:65px;text-align:right'; size.textContent=fmtBytes(r.size); row.appendChild(size);
        // Title
        const title=document.createElement('span'); title.style.cssText='flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'; title.textContent=r.title; title.title=r.title; row.appendChild(title);
        // Indexer
        const idx=document.createElement('span'); idx.style.cssText='min-width:80px;color:var(--text-dim);font-size:11px'; idx.textContent=r.indexer; row.appendChild(idx);
        // Action
        if(dec.accepted){
            const btn=document.createElement('button'); btn.className='btn btn-success btn-sm'; btn.textContent='Grab';
            btn.onclick=()=>grabRelease(r.download_url,r.title,r.quality); row.appendChild(btn);
        } else {
            const reason=document.createElement('span'); reason.style.cssText='font-size:10px;color:var(--red);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'; reason.textContent=dec.reason||''; reason.title=dec.reason||''; row.appendChild(reason);
        }
        body.appendChild(row);
    });
    panel.appendChild(body); rd.appendChild(panel);
}
async function grabRelease(url,title,quality) {
    const r=await apiPost('/downloads/grab',{download_url:url,title:title,quality:quality,media_type:'movie'});
    alert(r?.grabbed?'Grabbing: '+title:'Failed: '+(r?.reason||'unknown'));
}

// ── Downloads ──────────────────────────────────────────────
async function renderDownloads() {
    content.textContent='';
    const [downloads,speed]=await Promise.all([api('/downloads'),api('/downloads/speed')]);
    const dl=speed?(speed.dl_speed/1048576).toFixed(1):'0';
    const ul=speed?(speed.ul_speed/1048576).toFixed(1):'0';
    // Speed cards
    const stats=document.createElement('div'); stats.className='stat-row';
    [{l:'Download',v:dl+' MB/s',c:'var(--green)'},{l:'Upload',v:ul+' MB/s',c:'var(--accent)'},{l:'Active',v:String(downloads?.total||0),c:'var(--yellow)'}].forEach(s=>{
        const card=document.createElement('div'); card.className='stat-card';
        const bar=document.createElement('div'); bar.className='accent-bar'; bar.style.background=s.c; card.appendChild(bar);
        const lbl=document.createElement('div'); lbl.className='stat-label'; lbl.textContent=s.l; card.appendChild(lbl);
        const val=document.createElement('div'); val.className='stat-value'; val.textContent=s.v; card.appendChild(val);
        stats.appendChild(card);
    });
    content.appendChild(stats);
    // Torrent list
    const panel=document.createElement('div'); panel.className='panel';
    const head=document.createElement('div'); head.className='panel-header'; head.textContent='Torrents'; panel.appendChild(head);
    const body=document.createElement('div'); body.className='panel-body';
    if(downloads?.torrents?.length>0){
        downloads.torrents.slice(0,30).forEach(t=>{
            const row=document.createElement('div'); row.className='table-row';
            const st=document.createElement('span'); st.className='tag '+(t.state?.includes('UP')?'tag-green':t.state?.includes('DL')?'tag-blue':'tag-orange'); st.style.cssText='min-width:80px;text-align:center;font-size:9px'; st.textContent=t.state||''; row.appendChild(st);
            const nm=document.createElement('span'); nm.style.cssText='flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'; nm.textContent=t.name; row.appendChild(nm);
            const pc=document.createElement('span'); pc.style.cssText='min-width:50px;text-align:right'; pc.textContent=(t.progress*100).toFixed(1)+'%'; row.appendChild(pc);
            const sz=document.createElement('span'); sz.style.cssText='min-width:65px;text-align:right'; sz.textContent=fmtBytes(t.size); row.appendChild(sz);
            const sp=document.createElement('span'); sp.style.cssText='min-width:60px;text-align:right;color:var(--green)'; sp.textContent=(t.dl_speed/1048576).toFixed(1)+' MB/s'; row.appendChild(sp);
            body.appendChild(row);
        });
    } else { const e=document.createElement('div'); e.className='empty'; e.textContent='No downloads'; body.appendChild(e); }
    panel.appendChild(body); content.appendChild(panel);
}

// ── Indexers ───────────────────────────────────────────────
async function renderIndexers() {
    content.textContent='';
    const panel=document.createElement('div'); panel.className='panel';
    const head=document.createElement('div'); head.className='panel-header';
    const headText=document.createElement('span'); headText.textContent='Indexers'; head.appendChild(headText);
    const addBtn=document.createElement('button'); addBtn.className='btn btn-primary btn-sm'; addBtn.textContent='Add Indexer'; addBtn.onclick=showAddIndexer; head.appendChild(addBtn);
    panel.appendChild(head);
    const body=document.createElement('div'); body.className='panel-body';
    const indexers=await api('/indexers');
    if(indexers?.length>0){
        indexers.forEach(i=>{
            const row=document.createElement('div'); row.className='table-row';
            const tag=document.createElement('span'); tag.className='tag '+(i.enabled?'tag-green':'tag-red'); tag.textContent=i.enabled?'Enabled':'Disabled'; row.appendChild(tag);
            const nm=document.createElement('span'); nm.style.cssText='flex:1;font-weight:600'; nm.textContent=i.name; row.appendChild(nm);
            const tp=document.createElement('span'); tp.style.cssText='color:var(--text-dim);font-size:12px'; tp.textContent=i.type; row.appendChild(tp);
            const del=document.createElement('button'); del.className='btn btn-danger btn-sm'; del.textContent='Remove'; del.onclick=()=>{if(confirm('Remove '+i.name+'?'))apiDelete('/indexers/'+i.id).then(()=>renderIndexers());}; row.appendChild(del);
            body.appendChild(row);
        });
    } else { const e=document.createElement('div'); e.className='empty'; e.textContent='No indexers — add some to search for releases'; body.appendChild(e); }
    panel.appendChild(body); content.appendChild(panel);
    const formDiv=document.createElement('div'); formDiv.id='add-indexer-form'; content.appendChild(formDiv);
}
function showAddIndexer(){
    const form=document.getElementById('add-indexer-form'); form.textContent='';
    const panel=document.createElement('div'); panel.className='panel';
    const head=document.createElement('div'); head.className='panel-header'; head.textContent='Add Indexer'; panel.appendChild(head);
    const body=document.createElement('div'); body.className='panel-body'; body.style.cssText='display:grid;gap:8px;max-width:400px';
    const mkInput=(id,ph)=>{ const i=document.createElement('input'); i.className='search-input'; i.id=id; i.placeholder=ph; return i; };
    body.appendChild(mkInput('idx-name','Name (e.g. 1337x)'));
    body.appendChild(mkInput('idx-url','Torznab URL'));
    body.appendChild(mkInput('idx-key','API Key (optional)'));
    const btn=document.createElement('button'); btn.className='btn btn-success'; btn.textContent='Add'; btn.onclick=async()=>{
        const r=await apiPost('/indexers',{name:document.getElementById('idx-name').value,url:document.getElementById('idx-url').value,api_key:document.getElementById('idx-key').value});
        if(r?.added)renderIndexers(); else alert('Failed');
    }; body.appendChild(btn);
    panel.appendChild(body); form.appendChild(panel);
}

// ── Settings ───────────────────────────────────────────────
async function renderSettings() {
    content.textContent='';
    const [status,modules]=await Promise.all([api('/system/status'),api('/modules')]);
    // System info
    const sysPanel=document.createElement('div'); sysPanel.className='panel';
    const sysHead=document.createElement('div'); sysHead.className='panel-header'; sysHead.textContent='System Info'; sysPanel.appendChild(sysHead);
    const sysBody=document.createElement('div'); sysBody.className='panel-body';
    if(status){
        [['Version',status.version],['Database',status.database],['Media Root',status.media_root],['Downloads',status.download_dir],['Media Server',status.media_server],
         ['qBittorrent',status.download_client?(status.download_client.version+' ('+(status.download_client.connected?'connected':'offline')+')'):'N/A']
        ].forEach(([k,v])=>{
            const row=document.createElement('div'); row.className='table-row';
            const key=document.createElement('span'); key.textContent=k; row.appendChild(key);
            const spacer=document.createElement('span'); spacer.style.flex='1'; row.appendChild(spacer);
            const val=document.createElement('span'); val.textContent=v; row.appendChild(val);
            sysBody.appendChild(row);
        });
    }
    sysPanel.appendChild(sysBody); content.appendChild(sysPanel);
    // Modules
    const modPanel=document.createElement('div'); modPanel.className='panel';
    const modHead=document.createElement('div'); modHead.className='panel-header'; modHead.textContent='Modules'; modPanel.appendChild(modHead);
    const modBody=document.createElement('div'); modBody.className='panel-body';
    if(modules){
        Object.entries(modules).forEach(([name,mod])=>{
            const row=document.createElement('div'); row.className='table-row';
            const info=document.createElement('span'); info.style.flex='1';
            const title=document.createElement('strong'); title.textContent=mod.display_name; info.appendChild(title);
            info.appendChild(document.createElement('br'));
            const desc=document.createElement('span'); desc.style.cssText='font-size:11px;color:var(--text-dim)'; desc.textContent=mod.description; info.appendChild(desc);
            row.appendChild(info);
            const label=document.createElement('label'); label.style.cursor='pointer';
            const cb=document.createElement('input'); cb.type='checkbox'; cb.checked=mod.enabled;
            cb.onchange=async function(){ await apiPost('/modules/'+name+'/'+(this.checked?'enable':'disable')); renderSettings(); };
            label.appendChild(cb); label.appendChild(document.createTextNode(' '+(mod.enabled?'ON':'OFF')));
            row.appendChild(label);
            modBody.appendChild(row);
        });
    }
    modPanel.appendChild(modBody); content.appendChild(modPanel);
}

// ── Speed ticker ───────────────────────────────────────────
setInterval(async()=>{const s=await api('/downloads/speed');if(s)document.getElementById('dl-speed-mini').textContent=(s.dl_speed/1048576).toFixed(1)+' MB/s';},5000);

// ── Init ───────────────────────────────────────────────────
navigate('dashboard');
