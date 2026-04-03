// GrimmGear Mediarr — Frontend Application
// Phase B: Full interactive UI with detail pages, download controls, trending

const API = '/api';
const content = document.getElementById('content');
let currentPage = 'dashboard';

// ── API helpers ───────────────────────────────────────────
async function api(path) {
    try { const r = await fetch(API + path, {signal: AbortSignal.timeout(10000)}); return r.ok ? await r.json() : null; } catch { return null; }
}
async function apiPost(path, data) {
    try { const r = await fetch(API + path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(15000)}); return r.ok ? await r.json() : null; } catch { return null; }
}
async function apiDelete(path) {
    try { const r = await fetch(API + path, {method:'DELETE',signal: AbortSignal.timeout(10000)}); return r.ok ? await r.json() : null; } catch { return null; }
}
async function apiPut(path, data) {
    try { const r = await fetch(API + path, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(15000)}); return r.ok ? await r.json() : null; } catch { return null; }
}
function fmtBytes(b) { if(!b)return '0 B'; const u=['B','KB','MB','GB','TB']; const i=Math.floor(Math.log(b)/Math.log(1024)); return (b/Math.pow(1024,i)).toFixed(1)+' '+u[i]; }
function fmtSpeed(b) { return (b/1048576).toFixed(1)+' MB/s'; }
function fmtEta(s) { if(!s||s<=0||s>8640000) return ''; const h=Math.floor(s/3600); const m=Math.floor((s%3600)/60); return h>0?h+'h '+m+'m':m+'m'; }
function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function el(tag, cls, text) { const e=document.createElement(tag); if(cls)e.className=cls; if(text)e.textContent=text; return e; }

// ── Toast notifications ───────────────────────────────────
let toastContainer;
function toast(msg, type='') {
    if (!toastContainer) { toastContainer = el('div','toast-container'); document.body.appendChild(toastContainer); }
    const t = el('div','toast'+(type?' '+type:''), msg);
    toastContainer.appendChild(t);
    setTimeout(()=>{ t.style.opacity='0'; t.style.transition='opacity .3s'; setTimeout(()=>t.remove(),300); }, 3000);
}

// ── Navigation ────────────────────────────────────────────
function navigate(page) {
    currentPage = page;
    document.querySelectorAll('.nav-link').forEach(l => l.classList.toggle('active', l.dataset.page === page));
    // Close mobile sidebar
    document.getElementById('sidebar').classList.remove('open');
    const overlay = document.querySelector('.mobile-overlay');
    if (overlay) overlay.classList.remove('active');
    // Route
    const routes = {dashboard:renderDashboard,movies:renderMovies,tv:renderTV,music:renderMusic,books:renderBooks,comics:renderComics,search:renderSearch,downloads:renderDownloads,library:renderLibrary,calendar:renderCalendar,requests:renderRequests,indexers:renderIndexers,blocklist:renderBlocklist,system:renderSystem,settings:renderSettings};
    (routes[page]||renderDashboard)();
    window.location.hash = page;
}

// ── Dashboard ─────────────────────────────────────────────
async function renderDashboard() {
    content.textContent = '';

    const [status,health,movies,series,downloads,speed,scheduler] = await Promise.all([
        api('/system/status'),api('/system/health'),api('/movies'),api('/series'),
        api('/downloads'),api('/downloads/speed'),api('/scheduler/status')
    ]);

    const dlSpeed = speed ? fmtSpeed(speed.dl_speed) : '0 MB/s';
    document.getElementById('dl-speed-mini').textContent = dlSpeed;

    // Stats row
    const statsDiv = el('div','stat-row');
    const mkStat = (label,value,sub,color,click) => {
        const c=el('div','stat-card'); if(click)c.onclick=()=>navigate(click);
        const bar=el('div','accent-bar'); bar.style.background=color; c.appendChild(bar);
        c.appendChild(el('div','stat-label',label));
        c.appendChild(el('div','stat-value',String(value)));
        c.appendChild(el('div','stat-sub',sub));
        return c;
    };
    const movieCount = movies?movies.length:0;
    const movieFiles = movies?movies.filter(m=>m.has_file).length:0;
    statsDiv.appendChild(mkStat('Movies', movieCount, movieFiles+' on disk', 'var(--yellow)', 'movies'));
    statsDiv.appendChild(mkStat('TV Series', series?series.length:0, '', 'var(--cyan)', 'tv'));
    statsDiv.appendChild(mkStat('Downloads', dlSpeed, (downloads?downloads.total:0)+' active', 'var(--green)', 'downloads'));
    const healthColor = health?.status==='healthy'?'var(--green)':health?.status==='degraded'?'var(--orange)':'var(--red)';
    statsDiv.appendChild(mkStat('System', health?health.status:'?', 'Scheduler: '+(scheduler?.running?scheduler.tasks.length+' tasks':'off'), healthColor, 'settings'));
    content.appendChild(statsDiv);

    // Active downloads panel
    if (downloads?.torrents?.length > 0) {
        const dlPanel = el('div','panel');
        const dlHead = el('div','panel-header','Active Downloads ('+downloads.total+')');
        dlPanel.appendChild(dlHead);
        const dlBody = el('div','panel-body');
        const active = downloads.torrents.filter(t=>t.dl_speed>0||t.progress<1).slice(0,8);
        (active.length>0?active:downloads.torrents.slice(0,5)).forEach(t => {
            const row = el('div','dl-row');
            // State tag
            const stateTag = el('span','tag '+dlStateClass(t.state)); stateTag.style.minWidth='65px'; stateTag.style.textAlign='center'; stateTag.textContent=dlStateLabel(t.state); row.appendChild(stateTag);
            // Name
            const nm = el('span','dl-name',t.name); row.appendChild(nm);
            // Progress bar
            const prog = el('div','progress');
            const fill = el('div','progress-fill'+(t.progress>=1?' complete':t.state?.includes('paused')?' paused':' downloading'));
            fill.style.width = (t.progress*100)+'%'; prog.appendChild(fill); row.appendChild(prog);
            // Stats
            const stats = el('div','dl-stats');
            stats.appendChild(el('span','dl-stat',(t.progress*100).toFixed(0)+'%'));
            stats.appendChild(el('span','dl-stat',fmtSpeed(t.dl_speed)));
            row.appendChild(stats);
            dlBody.appendChild(row);
        });
        dlPanel.appendChild(dlBody);
        content.appendChild(dlPanel);
    }

    // Trending movies
    const trending = await api('/discover/movies/trending');
    if (trending?.length > 0) {
        const tPanel = el('div','panel');
        const tHead = el('div','panel-header','Trending Movies');
        tPanel.appendChild(tHead);
        const tBody = el('div','panel-body');
        const row = el('div','scroll-row');
        trending.slice(0,15).forEach(m => {
            const card = mkMediaCard(m.title, m.year, m.poster_url, false);
            card.onclick = () => showTMDBDetail('movie', m.tmdb_id);
            row.appendChild(card);
        });
        tBody.appendChild(row);
        tPanel.appendChild(tBody);
        content.appendChild(tPanel);
    }

    // Trending TV
    const trendingTV = await api('/discover/tv/trending');
    if (trendingTV?.length > 0) {
        const tvPanel = el('div','panel');
        tvPanel.appendChild(el('div','panel-header','Trending TV Shows'));
        const tvBody = el('div','panel-body');
        const row = el('div','scroll-row');
        trendingTV.slice(0,15).forEach(s => {
            const card = mkMediaCard(s.title, s.year, s.poster_url, false);
            card.onclick = () => showTMDBDetail('tv', s.tmdb_id);
            row.appendChild(card);
        });
        tvBody.appendChild(row);
        tvPanel.appendChild(tvBody);
        content.appendChild(tvPanel);
    }
}

// ── Media Card ────────────────────────────────────────────
function mkMediaCard(title, year, poster, hasFile) {
    const card = el('div','media-card');
    const img = document.createElement('img'); img.src=poster||''; img.alt=title; img.loading='lazy';
    img.onerror=function(){this.style.background='#333';this.src='';}; card.appendChild(img);
    if(hasFile){ const badge=el('div','card-badge tag-green','ON DISK'); card.appendChild(badge); }
    const info = el('div','card-info');
    info.appendChild(el('div','card-title',title));
    info.appendChild(el('div','card-year',year?String(year):''));
    card.appendChild(info);
    return card;
}

// ── Movies ────────────────────────────────────────────────
async function renderMovies() {
    content.textContent = '';
    content.appendChild(el('div','page-title','Movies'));

    // Search bar
    const box = el('div','search-box');
    const input = el('input','search-input'); input.id='movie-search'; input.placeholder='Search TMDB for movies to add...';
    input.onkeydown = e => { if(e.key==='Enter')searchMovies(); }; box.appendChild(input);
    const btn = el('button','btn btn-primary','Search'); btn.onclick=searchMovies; box.appendChild(btn);
    content.appendChild(box);
    content.appendChild(el('div','',''));
    const resultsDiv = el('div'); resultsDiv.id='movie-results'; content.appendChild(resultsDiv);

    // Library
    const movies = await api('/movies');
    const panel = el('div','panel');
    const head = el('div','panel-header','My Movies'+(movies?.length?' ('+movies.length+')':''));
    panel.appendChild(head);
    const body = el('div','panel-body');
    const grid = el('div','card-grid');
    if (movies?.length > 0) {
        movies.forEach(m => {
            const card = mkMediaCard(m.title, m.year, m.poster_url, m.has_file);
            card.onclick = () => showMovieDetail(m.id);
            grid.appendChild(card);
        });
    } else {
        grid.appendChild(el('div','empty','No movies yet — search above to add'));
    }
    body.appendChild(grid); panel.appendChild(body); content.appendChild(panel);

    // Update nav count
    updateNavCount('movies', movies?.length || 0);
}

async function searchMovies() {
    const q = document.getElementById('movie-search').value; if(!q) return;
    const rd = document.getElementById('movie-results'); rd.textContent='Searching TMDB...';
    const data = await api('/search?q='+encodeURIComponent(q)+'&type=movie');
    rd.textContent='';
    if(!data?.length){ rd.textContent='No results found.'; return; }
    const grid = el('div','card-grid');
    data.slice(0,20).forEach(m => {
        const card = mkMediaCard(m.title, (m.year||'')+(m.rating?' \u2014 \u2605'+m.rating.toFixed(1):''), m.poster_url, false);
        card.onclick = () => showTMDBDetail('movie', m.tmdb_id);
        grid.appendChild(card);
    });
    rd.appendChild(grid);
    rd.appendChild(el('div','page-subtitle','Click a movie to see details and add it'));
}

// ── TV Shows ──────────────────────────────────────────────
async function renderTV() {
    content.textContent='';
    content.appendChild(el('div','page-title','TV Shows'));

    const box = el('div','search-box');
    const input = el('input','search-input'); input.id='tv-search'; input.placeholder='Search TMDB for TV shows...';
    input.onkeydown=e=>{if(e.key==='Enter')searchTV();}; box.appendChild(input);
    const btn = el('button','btn btn-primary','Search'); btn.onclick=searchTV; box.appendChild(btn);
    content.appendChild(box);
    const rd = el('div'); rd.id='tv-results'; content.appendChild(rd);

    const series = await api('/series');
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header','My Series'+(series?.length?' ('+series.length+')':'')));
    const body = el('div','panel-body');
    const grid = el('div','card-grid');
    if(series?.length>0){
        series.forEach(s=>{
            const card = mkMediaCard(s.title,s.year,s.poster_url,false);
            card.onclick = () => showSeriesDetail(s.id);
            grid.appendChild(card);
        });
    } else { grid.appendChild(el('div','empty','No TV shows — search above')); }
    body.appendChild(grid); panel.appendChild(body); content.appendChild(panel);
    updateNavCount('tv', series?.length || 0);
}

async function searchTV() {
    const q=document.getElementById('tv-search').value; if(!q) return;
    const rd=document.getElementById('tv-results'); rd.textContent='Searching TMDB...';
    const data=await api('/search?q='+encodeURIComponent(q)+'&type=tv');
    rd.textContent='';
    if(!data?.length){rd.textContent='No results.'; return;}
    const grid = el('div','card-grid');
    data.slice(0,20).forEach(s=>{
        const card=mkMediaCard(s.title,(s.year||'')+(s.rating?' \u2014 \u2605'+s.rating.toFixed(1):''),s.poster_url,false);
        card.onclick=()=>showTMDBDetail('tv',s.tmdb_id);
        grid.appendChild(card);
    });
    rd.appendChild(grid);
    rd.appendChild(el('div','page-subtitle','Click a show to see details and add it'));
}

// ── Search Indexers ───────────────────────────────────────
async function renderSearch() {
    content.textContent='';
    content.appendChild(el('div','page-title','Search Indexers'));

    const box = el('div','search-box');
    const input = el('input','search-input'); input.id='idx-search'; input.placeholder='Search indexers (e.g. Inception 2010 1080p)...';
    input.onkeydown=e=>{if(e.key==='Enter')searchIndexers();}; box.appendChild(input);
    const btn = el('button','btn btn-primary','Search Indexers'); btn.onclick=searchIndexers; box.appendChild(btn);
    content.appendChild(box);
    content.appendChild(el('div','',''));
    const rd = el('div'); rd.id='idx-results'; content.appendChild(rd);
}

async function searchIndexers() {
    const q=document.getElementById('idx-search').value; if(!q) return;
    const rd=document.getElementById('idx-results'); rd.textContent='Searching indexers...';
    const data=await (async()=>{try{const r=await fetch(API+'/search/indexers?q='+encodeURIComponent(q),{signal:AbortSignal.timeout(60000)});return r.ok?await r.json():null;}catch{return null;}})();
    rd.textContent='';
    if(!data){ rd.textContent='Search timed out or failed. Try again.'; return; }
    if(!data?.results?.length){ rd.textContent='No results from '+(data?.indexers_searched||0)+' indexers.'; return; }
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header',data.total+' results from '+data.indexers_searched+' indexers'));
    const body = el('div','panel-body');
    data.results.slice(0,50).forEach(r => {
        const row = el('div','table-row');
        const dec=r.decision||{};
        const tag = el('span','tag '+(dec.accepted?'tag-green':'tag-red')); tag.style.cssText='min-width:55px;text-align:center'; tag.textContent=dec.accepted?'OK':'BLOCK'; row.appendChild(tag);
        const qual = el('span','tag tag-blue'); qual.style.cssText='min-width:50px;text-align:center'; qual.textContent=r.quality||'?'; row.appendChild(qual);
        const seed = el('span',''); seed.style.cssText='min-width:35px;text-align:right;color:var(--green);font-size:12px'; seed.textContent=r.seeders+'S'; row.appendChild(seed);
        const size = el('span',''); size.style.cssText='min-width:60px;text-align:right;font-size:12px'; size.textContent=fmtBytes(r.size); row.appendChild(size);
        const title = el('span',''); title.style.cssText='flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'; title.textContent=r.title; title.title=r.title; row.appendChild(title);
        const idx = el('span',''); idx.style.cssText='min-width:70px;color:var(--text-dim);font-size:11px'; idx.textContent=r.indexer; row.appendChild(idx);
        if(dec.accepted){
            const gbtn = el('button','btn btn-success btn-xs','Grab');
            gbtn.onclick=()=>grabRelease(r.download_url,r.title,r.quality); row.appendChild(gbtn);
        } else {
            const reason = el('span',''); reason.style.cssText='font-size:10px;color:var(--red);max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'; reason.textContent=dec.reason||''; reason.title=dec.reason||''; row.appendChild(reason);
        }
        body.appendChild(row);
    });
    panel.appendChild(body); rd.appendChild(panel);
}

async function grabRelease(url,title,quality) {
    const r=await apiPost('/downloads/grab',{download_url:url,title:title,quality:quality,media_type:'movie'});
    if(r?.grabbed) toast('Grabbing: '+title,'success'); else toast('Failed: '+(r?.reason||'unknown'),'error');
}

// ── Downloads ─────────────────────────────────────────────
async function renderDownloads() {
    content.textContent='';
    content.appendChild(el('div','page-title','Downloads'));

    const [downloads,speed]=await Promise.all([api('/downloads'),api('/downloads/speed')]);
    const dl=speed?fmtSpeed(speed.dl_speed):'0 MB/s';
    const ul=speed?fmtSpeed(speed.ul_speed):'0 MB/s';

    // Speed cards
    const stats = el('div','stat-row');
    [{l:'Download',v:dl,c:'var(--green)'},{l:'Upload',v:ul,c:'var(--accent)'},{l:'Active',v:String(downloads?.total||0),c:'var(--yellow)'},{l:'Total Data',v:speed?fmtBytes(speed.dl_total):'0',c:'var(--cyan)'}].forEach(s=>{
        const card = el('div','stat-card');
        const bar = el('div','accent-bar'); bar.style.background=s.c; card.appendChild(bar);
        card.appendChild(el('div','stat-label',s.l));
        card.appendChild(el('div','stat-value',s.v));
        stats.appendChild(card);
    });
    content.appendChild(stats);

    // Filter buttons
    const filterBar = el('div','btn-group'); filterBar.style.marginBottom='12px';
    ['All','Downloading','Seeding','Paused','Completed'].forEach(f=>{
        const btn = el('button','btn btn-ghost btn-sm',f);
        btn.onclick=()=>{
            filterBar.querySelectorAll('.btn').forEach(b=>b.classList.remove('btn-primary'));
            btn.classList.add('btn-primary'); btn.classList.remove('btn-ghost');
            filterDownloads(f.toLowerCase());
        };
        filterBar.appendChild(btn);
    });
    content.appendChild(filterBar);

    // Torrent list
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header','Torrents'));
    const body = el('div','panel-body'); body.id='dl-list';

    if(downloads?.torrents?.length>0){
        downloads.torrents.forEach(t => body.appendChild(mkDownloadRow(t)));
    } else { body.appendChild(el('div','empty','No downloads')); }

    panel.appendChild(body); content.appendChild(panel);
}

function mkDownloadRow(t) {
    const row = el('div','dl-row'); row.dataset.state=t.state||'';

    // State tag
    const stateTag = el('span','tag '+dlStateClass(t.state)); stateTag.style.cssText='min-width:70px;text-align:center;font-size:9px'; stateTag.textContent=dlStateLabel(t.state); row.appendChild(stateTag);

    // Name
    row.appendChild(el('span','dl-name',t.name));

    // Progress bar
    const prog = el('div','progress'); prog.style.maxWidth='120px';
    const fill = el('div','progress-fill'+(t.progress>=1?' complete':t.state?.includes('paused')?' paused':' downloading'));
    fill.style.width=(t.progress*100)+'%'; prog.appendChild(fill); row.appendChild(prog);

    // Stats
    const stats = el('div','dl-stats');
    stats.appendChild(el('span','dl-stat',(t.progress*100).toFixed(1)+'%'));
    stats.appendChild(el('span','dl-stat',fmtBytes(t.size)));
    const speedSpan = el('span','dl-stat'); speedSpan.style.color='var(--green)'; speedSpan.textContent=fmtSpeed(t.dl_speed); stats.appendChild(speedSpan);
    const eta = fmtEta(t.eta); if(eta){ stats.appendChild(el('span','dl-stat',eta)); }
    row.appendChild(stats);

    // Action buttons
    const actions = el('div','dl-actions');
    if(t.state?.includes('paused')||t.state?.includes('stopped')){
        const resumeBtn = el('button','btn btn-success btn-xs','\u25B6'); resumeBtn.title='Resume';
        resumeBtn.onclick=async(e)=>{e.stopPropagation();const r=await apiPost('/downloads/'+t.hash+'/resume');if(r?.resumed)toast('Resumed','success');renderDownloads();}; actions.appendChild(resumeBtn);
    } else if(t.progress<1) {
        const pauseBtn = el('button','btn btn-warning btn-xs','\u23F8'); pauseBtn.title='Pause';
        pauseBtn.onclick=async(e)=>{e.stopPropagation();const r=await apiPost('/downloads/'+t.hash+'/pause');if(r?.paused)toast('Paused','success');renderDownloads();}; actions.appendChild(pauseBtn);
    }
    const delBtn = el('button','btn btn-danger btn-xs','\u2715'); delBtn.title='Remove';
    delBtn.onclick=async(e)=>{e.stopPropagation();if(!confirm('Remove '+t.name+'?'))return;const r=await apiDelete('/downloads/'+t.hash);if(r?.deleted)toast('Removed','success');renderDownloads();}; actions.appendChild(delBtn);
    row.appendChild(actions);

    return row;
}

function filterDownloads(filter) {
    const rows = document.querySelectorAll('#dl-list .dl-row');
    rows.forEach(row => {
        const state = row.dataset.state||'';
        let show = true;
        if(filter==='downloading') show = state.includes('DL')||state.includes('downloading')||state.includes('metaDL');
        else if(filter==='seeding') show = state.includes('UP')||state.includes('uploading');
        else if(filter==='paused') show = state.includes('paused')||state.includes('stopped');
        else if(filter==='completed') show = state.includes('UP')||state.includes('completed');
        row.style.display = show ? '' : 'none';
    });
}

function dlStateClass(state) {
    if(!state) return 'tag-orange';
    if(state.includes('UP')||state.includes('uploading')) return 'tag-green';
    if(state.includes('DL')||state.includes('downloading')) return 'tag-blue';
    if(state.includes('paused')||state.includes('stopped')) return 'tag-orange';
    if(state.includes('stalled')) return 'tag-yellow';
    if(state.includes('error')) return 'tag-red';
    return 'tag-orange';
}
function dlStateLabel(state) {
    if(!state) return 'Unknown';
    if(state==='uploading'||state==='forcedUP') return 'Seeding';
    if(state==='stalledUP') return 'Seeded';
    if(state==='downloading'||state==='forcedDL') return 'Downloading';
    if(state==='stalledDL') return 'Stalled';
    if(state==='pausedDL'||state==='stoppedDL') return 'Paused';
    if(state==='pausedUP'||state==='stoppedUP') return 'Complete';
    if(state==='metaDL') return 'Metadata';
    if(state==='queuedDL') return 'Queued';
    if(state==='queuedUP') return 'Queued';
    if(state==='checkingDL'||state==='checkingUP') return 'Checking';
    if(state==='error'||state==='missingFiles') return 'Error';
    return state;
}

// ── Library ───────────────────────────────────────────────
async function renderLibrary() {
    content.textContent='';
    content.appendChild(el('div','page-title','Library'));
    content.appendChild(el('div','page-subtitle','What\u2019s on disk in your media directories'));

    const [stats,recent] = await Promise.all([api('/library/stats'),api('/library/recent?limit=25')]);

    // Stats overview
    if(stats){
        const row = el('div','stat-row');
        const typeMap = {movies:{label:'Movies',color:'var(--yellow)',icon:'\uD83C\uDFAC'},tv:{label:'TV Shows',color:'var(--cyan)',icon:'\uD83D\uDCFA'},music:{label:'Music',color:'var(--green)',icon:'\uD83C\uDFB5'},books:{label:'Books',color:'var(--accent)',icon:'\uD83D\uDCDA'}};
        for(const [key,info] of Object.entries(typeMap)){
            const s = stats[key]||{};
            const card = el('div','stat-card'); card.style.cursor='pointer';
            card.onclick=()=>showLibrarySection(key);
            const bar = el('div','accent-bar'); bar.style.background=info.color; card.appendChild(bar);
            card.appendChild(el('div','stat-label',info.icon+' '+info.label));
            card.appendChild(el('div','stat-value',String(s.folders||0)));
            card.appendChild(el('div','stat-sub',(s.files||0)+' files \u2022 '+fmtBytes(s.total_size||0)));
            row.appendChild(card);
        }
        content.appendChild(row);
    }

    // Recently added
    if(recent?.items?.length>0){
        const panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Recently Added'));
        const body = el('div','panel-body');
        recent.items.forEach(item => {
            const row = el('div','table-row');
            // Type tag
            const typeColors = {movie:'tag-yellow',tv:'tag-cyan',music:'tag-green',book:'tag-blue'};
            const typeLabels = {movie:'Movie',tv:'TV',music:'Music',book:'Book'};
            const tag = el('span','tag '+(typeColors[item.media_type]||'tag-blue')); tag.style.cssText='min-width:50px;text-align:center'; tag.textContent=typeLabels[item.media_type]||item.media_type; row.appendChild(tag);
            // Name
            const name = el('span','dl-name',item.name); row.appendChild(name);
            // Size
            row.appendChild(el('span','dl-stat',fmtBytes(item.total_size)));
            // Files count
            row.appendChild(el('span','dl-stat',item.file_count+' file'+(item.file_count!==1?'s':'')));
            // Date
            if(item.modified){
                const d = new Date(item.modified);
                const dateStr = d.toLocaleDateString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
                const dateSpan = el('span',''); dateSpan.style.cssText='min-width:100px;text-align:right;color:var(--text-dim);font-size:11px'; dateSpan.textContent=dateStr; row.appendChild(dateSpan);
            }
            body.appendChild(row);
        });
        panel.appendChild(body); content.appendChild(panel);
    }

    // Section containers for drill-down
    const sectionDiv = el('div'); sectionDiv.id='library-section'; content.appendChild(sectionDiv);
}

async function showLibrarySection(type) {
    const sectionDiv = document.getElementById('library-section');
    if(!sectionDiv) return;
    sectionDiv.textContent='Loading...';

    const endpointMap = {movies:'/library/movies',tv:'/library/tv',music:'/library/music',books:'/library/books'};
    const labelMap = {movies:'Movies',tv:'TV Shows',music:'Music',books:'Books'};
    const data = await api(endpointMap[type]);
    sectionDiv.textContent='';

    if(!data?.items?.length){
        sectionDiv.appendChild(el('div','empty','No '+labelMap[type]+' found in '+data?.path));
        return;
    }

    const panel = el('div','panel');
    const head = el('div','panel-header',labelMap[type]+' on Disk ('+data.total+')');
    // Path display
    const pathTag = el('span','tag tag-blue',data.path||''); head.appendChild(pathTag);
    panel.appendChild(head);
    const body = el('div','panel-body');

    // Sort by modified desc
    const items = data.items.sort((a,b) => (b.modified||'').localeCompare(a.modified||''));

    items.forEach(item => {
        const row = el('div','table-row'); row.style.cursor='pointer';

        // Folder/file icon
        const icon = el('span',''); icon.style.cssText='min-width:20px;text-align:center'; icon.textContent=item.type==='folder'?'\uD83D\uDCC1':'\uD83C\uDFA5'; row.appendChild(icon);

        // Name
        const name = el('span','dl-name',item.name); name.title=item.name; row.appendChild(name);

        // File count
        if(item.file_count > 0){
            row.appendChild(el('span','dl-stat',item.file_count+' file'+(item.file_count!==1?'s':'')));
        }

        // Size
        row.appendChild(el('span','dl-stat',fmtBytes(item.total_size)));

        // Modified date
        if(item.modified){
            const d = new Date(item.modified);
            const dateSpan = el('span',''); dateSpan.style.cssText='min-width:100px;text-align:right;color:var(--text-dim);font-size:11px';
            dateSpan.textContent=d.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
            row.appendChild(dateSpan);
        }

        // Click to browse folder contents (with playable files)
        row.onclick = () => browseFolder(item.path);

        body.appendChild(row);
    });

    panel.appendChild(body);
    sectionDiv.appendChild(panel);

    // Scroll to section
    sectionDiv.scrollIntoView({behavior:'smooth',block:'start'});
}

// ── Requests ──────────────────────────────────────────────
async function renderRequests() {
    content.textContent='';
    content.appendChild(el('div','page-title','Requests'));
    content.appendChild(el('div','page-subtitle','Request movies and TV shows. Search TMDB, submit, and admins approve.'));

    // Search bar
    const box = el('div','search-box');
    const input = el('input','search-input'); input.id='req-search'; input.placeholder='Search TMDB for a movie or show to request...';
    input.onkeydown=e=>{if(e.key==='Enter')searchForRequest();}; box.appendChild(input);
    const btn = el('button','btn btn-primary','Search'); btn.onclick=searchForRequest; box.appendChild(btn);
    content.appendChild(box);
    const rd = el('div'); rd.id='req-search-results'; content.appendChild(rd);

    // Existing requests
    const requests = await api('/requests');
    const pending = requests?.filter(r=>r.status==='pending')||[];
    const approved = requests?.filter(r=>r.status==='approved')||[];
    const denied = requests?.filter(r=>r.status==='denied')||[];

    if(pending.length > 0){
        const panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Pending Requests ('+pending.length+')'));
        const body = el('div','panel-body');
        pending.forEach(r => body.appendChild(mkRequestRow(r, true)));
        panel.appendChild(body); content.appendChild(panel);
    }
    if(approved.length > 0){
        const panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Approved ('+approved.length+')'));
        const body = el('div','panel-body');
        approved.forEach(r => body.appendChild(mkRequestRow(r, false)));
        panel.appendChild(body); content.appendChild(panel);
    }
    if(!requests?.length){
        content.appendChild(el('div','empty','No requests yet. Search above to request something.'));
    }
}

function mkRequestRow(r, showActions) {
    const row = el('div','table-row');
    const statusColors = {pending:'tag-yellow',approved:'tag-green',denied:'tag-red',available:'tag-cyan'};
    row.appendChild(el('span','tag '+(statusColors[r.status]||'tag-blue'),r.status));
    row.appendChild(el('span','tag tag-blue',r.media_type));
    if(r.poster_url){
        const img = document.createElement('img');
        img.src=r.poster_url; img.style.cssText='width:30px;height:45px;object-fit:cover;border-radius:3px;flex-shrink:0';
        row.appendChild(img);
    }
    const title = el('span','dl-name',r.title+(r.year?' ('+r.year+')':'')); row.appendChild(title);
    const voteBtn = el('button','btn btn-ghost btn-xs','\u2B06 '+r.votes);
    voteBtn.onclick=async(e)=>{e.stopPropagation();const res=await apiPost('/requests/'+r.id+'/vote');if(res)voteBtn.textContent='\u2B06 '+res.votes;};
    row.appendChild(voteBtn);
    row.appendChild(el('span','file-meta',r.requester));
    if(showActions){
        const approveBtn = el('button','btn btn-success btn-xs','Approve');
        approveBtn.onclick=async(e)=>{e.stopPropagation();const res=await apiPost('/requests/'+r.id+'/approve');if(res?.approved){toast('Approved: '+r.title+(res.added_to_library?' (added to library)':''),'success');renderRequests();}};
        row.appendChild(approveBtn);
        const denyBtn = el('button','btn btn-danger btn-xs','Deny');
        denyBtn.onclick=async(e)=>{e.stopPropagation();const res=await apiPost('/requests/'+r.id+'/deny');if(res?.denied){toast('Denied','');renderRequests();}};
        row.appendChild(denyBtn);
    }
    return row;
}

async function searchForRequest() {
    const q=document.getElementById('req-search').value; if(!q) return;
    const rd=document.getElementById('req-search-results'); rd.textContent='Searching...';
    const data = await api('/search?q='+encodeURIComponent(q));
    rd.textContent='';
    if(!data?.length){rd.textContent='No results.'; return;}
    const grid = el('div','card-grid');
    data.slice(0,12).forEach(item => {
        const card = mkMediaCard(item.title,(item.year||'')+(item.rating?' \u2014 \u2605'+item.rating.toFixed(1):''),item.poster_url,false);
        card.onclick = async () => {
            const r = await apiPost('/requests',{
                title:item.title, media_type:item.media_type||'movie',
                tmdb_id:item.tmdb_id, year:item.year||0,
                poster_url:item.poster_url||'', overview:item.overview||'',
                requester:'admin',
            });
            if(r?.created){ toast('Requested: '+item.title,'success'); renderRequests(); }
            else toast('Already requested or failed','error');
        };
        grid.appendChild(card);
    });
    rd.appendChild(grid);
    rd.appendChild(el('div','page-subtitle','Click to submit a request'));
}

// ── Indexers ──────────────────────────────────────────────
async function renderIndexers() {
    content.textContent='';
    content.appendChild(el('div','page-title','Indexers'));

    const [indexers, discovered, idxStats] = await Promise.all([api('/indexers'), api('/indexers/discover'), api('/indexers/stats')]);

    // Indexer stats overview (like Prowlarr)
    if(idxStats){
        const statsRow = el('div','stat-row');
        statsRow.appendChild(((label,val,color)=>{const c=el('div','stat-card');const b=el('div','accent-bar');b.style.background=color;c.appendChild(b);c.appendChild(el('div','stat-label',label));c.appendChild(el('div','stat-value',String(val)));return c;})('Total Queries',idxStats.total_queries,'var(--accent)'));
        statsRow.appendChild(((label,val,color)=>{const c=el('div','stat-card');const b=el('div','accent-bar');b.style.background=color;c.appendChild(b);c.appendChild(el('div','stat-label',label));c.appendChild(el('div','stat-value',String(val)));return c;})('Total Grabs',idxStats.total_grabs,'var(--green)'));
        statsRow.appendChild(((label,val,color)=>{const c=el('div','stat-card');const b=el('div','accent-bar');b.style.background=color;c.appendChild(b);c.appendChild(el('div','stat-label',label));c.appendChild(el('div','stat-value',String(val)));return c;})('Failures',idxStats.total_failures,'var(--red)'));
        statsRow.appendChild(((label,val,color)=>{const c=el('div','stat-card');const b=el('div','accent-bar');b.style.background=color;c.appendChild(b);c.appendChild(el('div','stat-label',label));c.appendChild(el('div','stat-value',String(val)));return c;})('Indexers',indexers?.length||0,'var(--cyan)'));
        content.appendChild(statsRow);
    }

    // Prowlarr auto-import banner
    if(discovered?.prowlarr_connected && discovered.total > 0){
        const banner = el('div','panel'); banner.style.cssText='border:1px solid var(--cyan);background:rgba(53,197,244,.05)';
        const bannerBody = el('div','panel-body'); bannerBody.style.cssText='display:flex;align-items:center;gap:12px';
        bannerBody.appendChild(el('span','tag tag-cyan','Prowlarr'));
        bannerBody.appendChild(el('span','',discovered.total+' indexers found at '+discovered.prowlarr_url));
        const importBtn = el('button','btn btn-primary btn-sm','Import All');
        importBtn.onclick = async () => {
            const r = await apiPost('/indexers/import-from-prowlarr');
            if(r){ toast('Imported '+r.imported+', skipped '+r.skipped+' (already exist)','success'); renderIndexers(); }
        };
        bannerBody.appendChild(importBtn);
        banner.appendChild(bannerBody); content.appendChild(banner);
    }

    // My indexers
    const panel = el('div','panel');
    const head = el('div','panel-header');
    head.appendChild(el('span','','My Indexers'+(indexers?.length?' ('+indexers.length+')':'')));
    const btnGroup = el('div','btn-group');
    const browseBtn = el('button','btn btn-primary btn-sm','Browse Catalog'); browseBtn.onclick=showIndexerCatalog; btnGroup.appendChild(browseBtn);
    const manualBtn = el('button','btn btn-ghost btn-sm','Add Manual'); manualBtn.onclick=showAddIndexerManual; btnGroup.appendChild(manualBtn);
    head.appendChild(btnGroup);
    panel.appendChild(head);

    const body = el('div','panel-body');
    if(indexers?.length>0){
        indexers.forEach(i=>{
            const row = el('div','table-row');
            const tag = el('span','tag '+(i.enabled?'tag-green':'tag-red')); tag.textContent=i.enabled?'Enabled':'Disabled'; row.appendChild(tag);
            const nm = el('span',''); nm.style.cssText='flex:1;font-weight:600'; nm.textContent=i.name; row.appendChild(nm);
            row.appendChild(el('span','tag tag-blue',i.type));
            if(i.use_flaresolverr) row.appendChild(el('span','tag tag-orange','CF'));
            // Per-indexer stats
            if(i.stats){
                const st=i.stats;
                row.appendChild(el('span','dl-stat',st.queries+'Q'));
                row.appendChild(el('span','dl-stat',st.grabs+'G'));
                if(st.failures>0) row.appendChild(el('span','dl-stat',st.failures+'F'));
                if(st.avg_response_ms>0) row.appendChild(el('span','dl-stat',st.avg_response_ms+'ms'));
            }
            // Test button
            const testBtn = el('button','btn btn-ghost btn-xs','Test');
            testBtn.onclick=async(e)=>{
                e.stopPropagation(); testBtn.textContent='Testing...';
                const r=await apiPost('/indexers/'+i.id+'/test');
                if(r?.success){ testBtn.textContent=r.results+' results'; testBtn.className='btn btn-success btn-xs'; toast(i.name+': '+r.results+' results','success'); }
                else { testBtn.textContent='Failed'; testBtn.className='btn btn-danger btn-xs'; toast(i.name+': '+(r?.error||'failed'),'error'); }
            };
            row.appendChild(testBtn);
            const del = el('button','btn btn-danger btn-xs','Remove'); del.onclick=()=>{if(confirm('Remove '+i.name+'?'))apiDelete('/indexers/'+i.id).then(()=>renderIndexers());}; row.appendChild(del);
            body.appendChild(row);
        });
    } else {
        body.appendChild(el('div','empty','No indexers configured. Browse the catalog or import from Prowlarr.'));
    }
    panel.appendChild(body); content.appendChild(panel);

    // Catalog / manual form container
    const formDiv = el('div'); formDiv.id='indexer-form-area'; content.appendChild(formDiv);
}

async function showIndexerCatalog() {
    const area = document.getElementById('indexer-form-area'); if(!area) return;
    area.textContent='Loading catalog...';
    const data = await api('/indexers/catalog');
    area.textContent='';
    if(!data?.indexers?.length){ area.textContent='No indexers in catalog'; return; }

    const panel = el('div','panel');
    const head = el('div','panel-header');
    head.appendChild(el('span','','Indexer Catalog ('+data.total+')'));

    // Category filter
    const filterBar = el('div','btn-group'); filterBar.style.marginLeft='auto';
    ['All','Movies','TV','Music','Anime','Books'].forEach(cat=>{
        const btn = el('button','btn btn-ghost btn-xs',cat);
        btn.onclick = async () => {
            filterBar.querySelectorAll('.btn').forEach(b=>{b.classList.remove('btn-primary');b.classList.add('btn-ghost');});
            btn.classList.add('btn-primary'); btn.classList.remove('btn-ghost');
            const filtered = cat==='All'? await api('/indexers/catalog') : await api('/indexers/catalog?category='+cat);
            renderCatalogGrid(body, filtered?.indexers||[]);
        };
        filterBar.appendChild(btn);
    });
    head.appendChild(filterBar);
    panel.appendChild(head);

    const body = el('div','panel-body');
    renderCatalogGrid(body, data.indexers);
    panel.appendChild(body);
    area.appendChild(panel);
    area.scrollIntoView({behavior:'smooth'});
}

function renderCatalogGrid(container, indexers) {
    container.textContent='';
    const grid = el('div',''); grid.style.cssText='display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px';
    indexers.forEach(idx => {
        const card = el('div','stat-card'); card.style.cssText='cursor:pointer;padding:14px';
        // Header row
        const headerRow = el('div',''); headerRow.style.cssText='display:flex;align-items:center;gap:8px;margin-bottom:6px';
        headerRow.appendChild(el('strong','',idx.name));
        const privacyTag = el('span','tag '+(idx.privacy==='public'?'tag-green':idx.privacy==='semi-private'?'tag-yellow':'tag-orange'),idx.privacy);
        headerRow.appendChild(privacyTag);
        if(idx.protocol==='usenet') headerRow.appendChild(el('span','tag tag-cyan','Usenet'));
        card.appendChild(headerRow);
        // Description
        card.appendChild(el('div','page-subtitle',idx.description));
        // Categories
        const catRow = el('div',''); catRow.style.cssText='display:flex;flex-wrap:wrap;gap:4px;margin-top:6px';
        idx.categories.forEach(c=>catRow.appendChild(el('span','tag tag-blue',c)));
        card.appendChild(catRow);
        // Add button
        card.onclick = () => addFromCatalog(idx);
        grid.appendChild(card);
    });
    container.appendChild(grid);
}

async function addFromCatalog(idx) {
    // Check if we have this indexer in Prowlarr
    const disc = await api('/indexers/discover');
    const prowlarrMatch = disc?.discovered?.find(d => d.name.toLowerCase() === idx.name.toLowerCase());

    if(prowlarrMatch){
        // Auto-add via Prowlarr torznab URL
        const r = await apiPost('/indexers', {name: idx.name, url: prowlarrMatch.torznab_url, indexer_type: 'torznab'});
        if(r?.added){ toast('Added '+idx.name+' via Prowlarr','success'); renderIndexers(); }
        else toast('Failed to add (may already exist)','error');
    } else if(idx.needs_api_key) {
        // Show config form for private indexers
        showIndexerConfigForm(idx);
    } else {
        // Public indexer without Prowlarr — needs Jackett or manual URL
        toast(idx.name+' requires Prowlarr or Jackett for Torznab access. Import from Prowlarr above, or add the Torznab URL manually.','error');
    }
}

function showIndexerConfigForm(idx) {
    const area = document.getElementById('indexer-form-area'); if(!area) return;
    // Append config form
    const panel = el('div','panel'); panel.style.marginTop='12px';
    panel.appendChild(el('div','panel-header','Configure '+idx.name));
    const body = el('div','panel-body'); body.style.cssText='display:grid;gap:8px;max-width:400px';
    body.appendChild(el('div','page-subtitle',idx.description+' — requires API key or credentials'));
    const mkInput=(id,ph)=>{ const i=el('input','search-input'); i.id=id; i.placeholder=ph; return i; };
    body.appendChild(mkInput('cat-url','Torznab URL'));
    body.appendChild(mkInput('cat-key','API Key'));
    const btn = el('button','btn btn-success','Add '+idx.name);
    btn.onclick = async () => {
        const url = document.getElementById('cat-url').value;
        const key = document.getElementById('cat-key').value;
        if(!url){ toast('Torznab URL required','error'); return; }
        const r = await apiPost('/indexers', {name: idx.name, url: url, api_key: key, indexer_type: 'torznab'});
        if(r?.added){ toast('Added: '+idx.name,'success'); renderIndexers(); } else toast('Failed','error');
    };
    body.appendChild(btn);
    panel.appendChild(body);
    area.appendChild(panel);
}

function showAddIndexerManual(){
    const area = document.getElementById('indexer-form-area'); if(!area) return;
    area.textContent='';
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header','Add Indexer Manually'));
    const body = el('div','panel-body'); body.style.cssText='display:grid;gap:8px;max-width:400px';
    const mkInput=(id,ph)=>{ const i=el('input','search-input'); i.id=id; i.placeholder=ph; return i; };
    body.appendChild(mkInput('idx-name','Name (e.g. 1337x)'));
    body.appendChild(mkInput('idx-url','Torznab URL'));
    body.appendChild(mkInput('idx-key','API Key (optional)'));
    const btn = el('button','btn btn-success','Add Indexer');
    btn.onclick=async()=>{
        const name=document.getElementById('idx-name').value, url=document.getElementById('idx-url').value;
        if(!name||!url){ toast('Name and URL required','error'); return; }
        const r=await apiPost('/indexers',{name:name,url:url,api_key:document.getElementById('idx-key').value});
        if(r?.added){ toast('Added: '+r.name,'success'); renderIndexers(); } else toast('Failed to add indexer','error');
    };
    body.appendChild(btn);
    panel.appendChild(body); area.appendChild(panel);
}

// ── Settings ──────────────────────────────────────────────
async function renderSettings() {
    content.textContent='';
    content.appendChild(el('div','page-title','Settings'));

    // Settings tabs
    const tabs = el('div','btn-group'); tabs.style.cssText='margin-bottom:16px;flex-wrap:wrap';
    const sections = ['Media Management','Download Clients','Media Server','Notifications','Quality','Modules','System'];
    sections.forEach((name,i) => {
        const btn = el('button','btn '+(i===0?'btn-primary':'btn-ghost')+' btn-sm',name);
        btn.onclick = () => {
            tabs.querySelectorAll('.btn').forEach(b=>{b.className='btn btn-ghost btn-sm';});
            btn.className='btn btn-primary btn-sm';
            document.querySelectorAll('.settings-section').forEach(s=>s.style.display='none');
            document.getElementById('settings-'+i).style.display='';
        };
        tabs.appendChild(btn);
    });
    content.appendChild(tabs);

    // Container for all sections
    const container = el('div','');

    // ── Section 0: Media Management ──────────────────
    const s0 = el('div','settings-section'); s0.id='settings-0';
    // Root folders
    const rfPanel = el('div','panel');
    const rfHead = el('div','panel-header');
    rfHead.appendChild(el('span','','Root Folders'));
    const addRfBtn = el('button','btn btn-primary btn-sm','+ Add Folder');
    addRfBtn.onclick = () => showAddRootFolder();
    rfHead.appendChild(addRfBtn);
    rfPanel.appendChild(rfHead);
    const rfBody = el('div','panel-body');
    const rootFolders = await api('/settings/rootfolders');
    if(rootFolders?.folders?.length > 0){
        rootFolders.folders.forEach(rf => {
            const row = el('div','table-row');
            row.appendChild(el('span','tag tag-blue',rf.media_type));
            const pathSpan = el('span','dl-name',rf.path); row.appendChild(pathSpan);
            row.appendChild(el('span','tag '+(rf.exists?'tag-green':'tag-red'),rf.exists?'OK':'Missing'));
            row.appendChild(el('span','dl-stat',fmtBytes(rf.free_space)+' free'));
            const delBtn = el('button','btn btn-danger btn-xs','Remove');
            delBtn.onclick=async()=>{await apiDelete('/settings/rootfolders/'+rf.id);renderSettings();};
            row.appendChild(delBtn);
            rfBody.appendChild(row);
        });
    } else {
        rfBody.appendChild(el('div','empty','No root folders configured. Add folders to tell Mediarr where your media lives.'));
    }
    rfPanel.appendChild(rfBody);
    s0.appendChild(rfPanel);

    // Add root folder form
    const rfForm = el('div'); rfForm.id='add-rf-form'; s0.appendChild(rfForm);

    // General paths
    const genSettings = await api('/settings/general');
    const gpPanel = el('div','panel');
    gpPanel.appendChild(el('div','panel-header','General Paths'));
    const gpBody = el('div','panel-body'); gpBody.style.cssText='display:grid;gap:8px;max-width:500px';
    const mkField = (label,id,val) => {
        const wrap=el('div',''); wrap.style.cssText='display:flex;align-items:center;gap:8px';
        wrap.appendChild(el('label','',label)); const lbl=wrap.firstChild; lbl.style.cssText='min-width:110px;font-size:13px;color:var(--text-dim)';
        const inp=el('input','search-input'); inp.id=id; inp.value=val||''; inp.style.flex='1'; wrap.appendChild(inp);
        return wrap;
    };
    gpBody.appendChild(mkField('Media Root','gen-media-root',genSettings?.media_root||''));
    gpBody.appendChild(mkField('Download Dir','gen-dl-dir',genSettings?.download_dir||''));
    gpBody.appendChild(mkField('DLNA Name','gen-dlna-name',genSettings?.dlna_name||''));
    const saveGenBtn = el('button','btn btn-success btn-sm','Save Paths');
    saveGenBtn.onclick = async () => {
        const r = await fetch(API+'/settings/general',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({
            media_root:document.getElementById('gen-media-root').value,
            download_dir:document.getElementById('gen-dl-dir').value,
            dlna_name:document.getElementById('gen-dlna-name').value,
        })});
        toast(r.ok?'Paths saved (restart to apply)':'Failed to save','success');
    };
    gpBody.appendChild(saveGenBtn);
    gpPanel.appendChild(gpBody); s0.appendChild(gpPanel);
    container.appendChild(s0);

    // ── Section 1: Download Clients ──────────────────
    const s1 = el('div','settings-section'); s1.id='settings-1'; s1.style.display='none';
    const dcPanel = el('div','panel');
    const dcHead = el('div','panel-header');
    dcHead.appendChild(el('span','','Download Clients'));
    const addDcBtn = el('button','btn btn-primary btn-sm','+ Add Client');
    addDcBtn.onclick = () => showAddDownloadClient();
    dcHead.appendChild(addDcBtn);
    dcPanel.appendChild(dcHead);
    const dcBody = el('div','panel-body');
    const dlClients = await api('/settings/downloadclients');
    if(dlClients?.length > 0){
        dlClients.forEach(c => {
            const row = el('div','table-row');
            row.appendChild(el('span','tag '+(c.enabled?'tag-green':'tag-red'),c.enabled?'ON':'OFF'));
            row.appendChild(el('span','tag tag-blue',c.client_type));
            row.appendChild(el('span','dl-name',c.name+' ('+c.host+':'+c.port+')'));
            row.appendChild(el('span','dl-stat','cat: '+c.category));
            const delBtn = el('button','btn btn-danger btn-xs','Remove');
            delBtn.onclick=async()=>{await apiDelete('/settings/downloadclients/'+c.id);renderSettings();};
            row.appendChild(delBtn);
            dcBody.appendChild(row);
        });
    } else {
        dcBody.appendChild(el('div','empty','No download clients. Add qBittorrent, SABnzbd, or other clients.'));
    }
    dcPanel.appendChild(dcBody);
    s1.appendChild(dcPanel);
    const dcForm = el('div'); dcForm.id='add-dc-form'; s1.appendChild(dcForm);
    container.appendChild(s1);

    // ── Section 2: Media Server ──────────────────────
    const s2 = el('div','settings-section'); s2.id='settings-2'; s2.style.display='none';
    const msPanel = el('div','panel');
    msPanel.appendChild(el('div','panel-header','Media Server Connection'));
    const msBody = el('div','panel-body'); msBody.style.cssText='display:grid;gap:8px;max-width:500px';
    const msConfig = await api('/settings/mediaserver');
    const msType = el('select','search-input'); msType.id='ms-type';
    ['built-in','plex','jellyfin','emby'].forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t.charAt(0).toUpperCase()+t.slice(1);if(t===msConfig?.type)o.selected=true;msType.appendChild(o);});
    msBody.appendChild(mkField('Type','ms-type-wrap',''));
    msBody.lastChild.querySelector('input')?.remove(); msBody.lastChild.appendChild(msType);
    msBody.appendChild(mkField('URL','ms-url',msConfig?.url||''));
    msBody.appendChild(mkField('Token','ms-token',''));
    document.getElementById('ms-token')&&(document.getElementById('ms-token').type='password');
    if(msConfig?.has_token) { const hint=el('div','page-subtitle','Token is set. Leave blank to keep current.'); msBody.appendChild(hint); }
    const msBtns = el('div','btn-group');
    const msTestBtn = el('button','btn btn-ghost btn-sm','Test Connection');
    msTestBtn.onclick = async () => {
        msTestBtn.textContent='Testing...';
        const r = await apiPost('/settings/mediaserver/test',{type:msType.value,url:document.getElementById('ms-url').value,token:document.getElementById('ms-token').value||'placeholder'});
        msTestBtn.textContent=r?.success?'Connected!':'Failed';
        msTestBtn.className='btn '+(r?.success?'btn-success':'btn-danger')+' btn-sm';
        toast(r?.message||'Test complete',r?.success?'success':'error');
    };
    msBtns.appendChild(msTestBtn);
    const msSaveBtn = el('button','btn btn-success btn-sm','Save');
    msSaveBtn.onclick = async () => {
        const r = await fetch(API+'/settings/mediaserver',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({
            type:msType.value,url:document.getElementById('ms-url').value,token:document.getElementById('ms-token').value,
        })});
        toast(r.ok?'Media server saved':'Failed','success');
    };
    msBtns.appendChild(msSaveBtn);
    const plexScanBtn = el('button','btn btn-primary btn-sm','Scan Plex Library');
    plexScanBtn.onclick=async()=>{const r=await apiPost('/plex/scan');toast(r?.triggered?'Scan triggered':'Not configured','');};
    msBtns.appendChild(plexScanBtn);
    msBody.appendChild(msBtns);
    msPanel.appendChild(msBody); s2.appendChild(msPanel);
    container.appendChild(s2);

    // ── Section 3: Notifications ─────────────────────
    const s3 = el('div','settings-section'); s3.id='settings-3'; s3.style.display='none';
    const ntPanel = el('div','panel');
    const ntHead = el('div','panel-header');
    ntHead.appendChild(el('span','','Notification Channels'));
    const addNtBtn = el('button','btn btn-primary btn-sm','+ Add Channel');
    addNtBtn.onclick = () => showAddNotification();
    ntHead.appendChild(addNtBtn);
    ntPanel.appendChild(ntHead);
    const ntBody = el('div','panel-body');
    const agents = await api('/settings/notifications');
    if(agents?.length > 0){
        agents.forEach(a => {
            const row = el('div','table-row');
            row.appendChild(el('span','tag '+(a.enabled?'tag-green':'tag-red'),a.enabled?'ON':'OFF'));
            row.appendChild(el('span','tag tag-blue',a.agent_type));
            row.appendChild(el('span','dl-name',a.name));
            const testBtn = el('button','btn btn-ghost btn-xs','Test');
            testBtn.onclick=async()=>{testBtn.textContent='...';const r=await apiPost('/settings/notifications/'+a.id+'/test');toast(r?.success?'Sent!':'Failed','');testBtn.textContent='Test';};
            row.appendChild(testBtn);
            const delBtn = el('button','btn btn-danger btn-xs','Remove');
            delBtn.onclick=async()=>{await apiDelete('/settings/notifications/'+a.id);renderSettings();};
            row.appendChild(delBtn);
            ntBody.appendChild(row);
        });
    } else { ntBody.appendChild(el('div','empty','No notification channels configured.')); }
    ntPanel.appendChild(ntBody); s3.appendChild(ntPanel);
    const ntForm = el('div'); ntForm.id='add-nt-form'; s3.appendChild(ntForm);
    container.appendChild(s3);

    // ── Section 4: Quality Profiles ──────────────────
    const s4 = el('div','settings-section'); s4.id='settings-4'; s4.style.display='none';
    const qpPanel = el('div','panel');
    const qpHead = el('div','panel-header');
    qpHead.appendChild(el('span','','Quality Profiles'));
    const addQpBtn = el('button','btn btn-primary btn-sm','+ Add Profile');
    addQpBtn.onclick = () => showAddQualityProfile();
    qpHead.appendChild(addQpBtn);
    qpPanel.appendChild(qpHead);
    const qpBody = el('div','panel-body');
    const profiles = await api('/qualityprofiles');
    if(profiles?.length > 0){
        profiles.forEach(p => {
            const row = el('div','table-row');
            row.appendChild(el('strong','',p.name));
            const spacer=el('span','');spacer.style.flex='1';row.appendChild(spacer);
            row.appendChild(el('span','tag tag-blue',p.language));
            row.appendChild(el('span','dl-stat','Min: '+p.cutoff));
            row.appendChild(el('span','tag '+(p.upgrade_allowed?'tag-green':'tag-orange'),p.upgrade_allowed?'Upgrade':'No Upgrade'));
            const delBtn = el('button','btn btn-danger btn-xs','Remove');
            delBtn.onclick=async()=>{await apiDelete('/qualityprofiles/'+p.id);renderSettings();};
            row.appendChild(delBtn);
            qpBody.appendChild(row);
        });
    } else { qpBody.appendChild(el('div','empty','No quality profiles.')); }
    qpPanel.appendChild(qpBody); s4.appendChild(qpPanel);
    const qpForm = el('div'); qpForm.id='add-qp-form'; s4.appendChild(qpForm);
    container.appendChild(s4);

    // ── Section 5: Modules ───────────────────────────
    const s5 = el('div','settings-section'); s5.id='settings-5'; s5.style.display='none';
    const modPanel = el('div','panel');
    modPanel.appendChild(el('div','panel-header','Modules'));
    const modBody = el('div','panel-body');
    const modules = await api('/modules');
    if(modules){
        Object.entries(modules).forEach(([name,mod])=>{
            const row = el('div','table-row');
            const info = el('span',''); info.style.flex='1';
            info.appendChild(el('strong','',mod.display_name));
            info.appendChild(document.createElement('br'));
            const desc=el('span','',mod.description);desc.style.cssText='font-size:11px;color:var(--text-dim)';info.appendChild(desc);
            row.appendChild(info);
            const label=el('label','');label.style.cssText='cursor:pointer;display:flex;align-items:center;gap:6px';
            const cb=document.createElement('input');cb.type='checkbox';cb.checked=mod.enabled;
            cb.onchange=async function(){await apiPost('/modules/'+name+'/'+(this.checked?'enable':'disable'));toast(mod.display_name+' '+(this.checked?'enabled':'disabled'),'success');};
            label.appendChild(cb);
            label.appendChild(el('span','tag '+(mod.enabled?'tag-green':'tag-orange'),mod.enabled?'ON':'OFF'));
            row.appendChild(label);
            modBody.appendChild(row);
        });
    }
    modPanel.appendChild(modBody); s5.appendChild(modPanel);
    container.appendChild(s5);

    // ── Section 6: System ────────────────────────────
    const s6 = el('div','settings-section'); s6.id='settings-6'; s6.style.display='none';
    const [status,health,scheduler,tcStatus,disk] = await Promise.all([
        api('/system/status'),api('/system/health'),api('/scheduler/status'),api('/transcode/status'),api('/cleanup/disk')
    ]);
    // System info
    const sysPanel = el('div','panel');
    sysPanel.appendChild(el('div','panel-header','System Info'));
    const sysBody = el('div','panel-body');
    if(status){
        [['Version',status.version],['Database',status.database],['qBittorrent',status.download_client?(status.download_client.version+' ('+(status.download_client.connected?'connected':'offline')+')'):'N/A'],
         ['Health',health?.status||'?'],['Scheduler',scheduler?.running?scheduler.tasks?.length+' tasks running':'off'],
         ['FFmpeg',tcStatus?.ffmpeg||'not found'],['Last Import',scheduler?.last_import_scan||'never'],['Last RSS Sync',scheduler?.last_rss_sync||'never'],
        ].forEach(([k,v])=>{
            const row=el('div','table-row');row.appendChild(el('span','',k));const sp=el('span','');sp.style.flex='1';row.appendChild(sp);
            const val=el('span','',String(v));val.style.color='var(--text-bright)';row.appendChild(val);sysBody.appendChild(row);
        });
    }
    // Disk usage
    if(disk){
        for(const [name,info] of Object.entries(disk)){
            if(info.error) continue;
            const row=el('div','table-row');
            row.appendChild(el('span','',name.charAt(0).toUpperCase()+name.slice(1)+' ('+info.path+')'));
            const sp=el('span','');sp.style.flex='1';row.appendChild(sp);
            const prog=el('div','progress');prog.style.maxWidth='100px';
            const fill=el('div','progress-fill'+(info.percent>90?' paused':info.percent>70?' downloading':' complete'));
            fill.style.width=info.percent+'%';prog.appendChild(fill);row.appendChild(prog);
            row.appendChild(el('span','dl-stat',info.percent+'%'));
            row.appendChild(el('span','dl-stat',fmtBytes(info.free)+' free'));
            sysBody.appendChild(row);
        }
    }
    sysPanel.appendChild(sysBody); s6.appendChild(sysPanel);
    container.appendChild(s6);

    content.appendChild(container);
}

// ── Settings: Add Root Folder Form ────────────────────────
async function showAddRootFolder() {
    const form = document.getElementById('add-rf-form'); if(!form) return;
    form.textContent='';
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header','Add Root Folder'));
    const body = el('div','panel-body'); body.style.cssText='display:grid;gap:8px;max-width:500px';
    // Type selector
    const typeWrap = el('div',''); typeWrap.style.cssText='display:flex;gap:8px';
    const typeSelect = el('select','search-input'); typeSelect.id='rf-type';
    ['movie','tv','music','books','comics'].forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t.charAt(0).toUpperCase()+t.slice(1);typeSelect.appendChild(o);});
    typeWrap.appendChild(el('label','','Type:')); typeWrap.firstChild.style.cssText='min-width:60px;font-size:13px;color:var(--text-dim);display:flex;align-items:center';
    typeWrap.appendChild(typeSelect);
    body.appendChild(typeWrap);
    // Path input + browse
    const pathWrap = el('div',''); pathWrap.style.cssText='display:flex;gap:8px';
    const pathInput = el('input','search-input'); pathInput.id='rf-path'; pathInput.placeholder='D:\\Media\\Movies'; pathInput.style.flex='1';
    pathWrap.appendChild(pathInput);
    const browseBtn = el('button','btn btn-ghost btn-sm','Browse...');
    browseBtn.onclick = () => showFolderPicker('rf-path');
    pathWrap.appendChild(browseBtn);
    body.appendChild(pathWrap);
    // Save button
    const saveBtn = el('button','btn btn-success','Add Root Folder');
    saveBtn.onclick = async () => {
        const path = document.getElementById('rf-path').value;
        const type = document.getElementById('rf-type').value;
        if(!path){toast('Path required','error');return;}
        const r = await apiPost('/settings/rootfolders',{path:path,media_type:type});
        if(r?.added){toast('Added: '+path,'success');renderSettings();} else toast('Failed','error');
    };
    body.appendChild(saveBtn);
    panel.appendChild(body); form.appendChild(panel);
    form.scrollIntoView({behavior:'smooth'});
}

async function showFolderPicker(targetInputId) {
    const overlay = el('div','modal-overlay');
    overlay.onclick = e => {if(e.target===overlay)overlay.remove();};
    const modal = el('div','modal'); modal.style.cssText='max-width:500px;padding:20px;max-height:70vh;overflow-y:auto';
    modal.appendChild(el('div','detail-title','Select Folder'));

    async function loadDir(path) {
        modal.querySelectorAll('.folder-list').forEach(e=>e.remove());
        const data = await api('/settings/browse?path='+encodeURIComponent(path||''));
        if(!data) return;
        const list = el('div','folder-list');
        if(data.parent){
            const backRow = el('div','file-row');
            backRow.appendChild(el('span','file-icon','\u2190'));
            backRow.appendChild(el('span','file-name','.. (up)'));
            backRow.onclick = () => loadDir(data.parent);
            list.appendChild(backRow);
        }
        // Current path display
        const curPath = el('div',''); curPath.style.cssText='padding:8px 0;font-size:12px;color:var(--text-dim)';
        curPath.textContent = data.path || 'Drives'; list.appendChild(curPath);

        data.items.forEach(item => {
            const row = el('div','file-row');
            row.appendChild(el('span','file-icon',item.type==='drive'?'\uD83D\uDCBB':'\uD83D\uDCC1'));
            const name = el('span','file-name',item.name); row.appendChild(name);
            if(item.free) row.appendChild(el('span','file-meta',fmtBytes(item.free)+' free'));
            row.onclick = () => loadDir(item.path);
            list.appendChild(row);
        });

        // Select this folder button
        if(data.path){
            const selectBtn = el('button','btn btn-success','Select This Folder: '+data.path.split(/[\\/]/).pop());
            selectBtn.style.cssText='margin-top:12px;width:100%';
            selectBtn.onclick = () => { document.getElementById(targetInputId).value=data.path; overlay.remove(); };
            list.appendChild(selectBtn);
        }
        modal.appendChild(list);
    }

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    loadDir('');
}

// ── Settings: Add Download Client Form ────────────────────
function showAddDownloadClient() {
    const form = document.getElementById('add-dc-form'); if(!form) return;
    form.textContent='';
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header','Add Download Client'));
    const body = el('div','panel-body'); body.style.cssText='display:grid;gap:8px;max-width:500px';
    const typeSelect = el('select','search-input'); typeSelect.id='dc-type';
    [['qbittorrent','qBittorrent'],['sabnzbd','SABnzbd'],['transmission','Transmission'],['deluge','Deluge'],['nzbget','NZBGet']].forEach(([v,l])=>{
        const o=document.createElement('option');o.value=v;o.textContent=l;typeSelect.appendChild(o);
    });
    body.appendChild(typeSelect);
    const mkI=(id,ph,type)=>{const i=el('input','search-input');i.id=id;i.placeholder=ph;if(type)i.type=type;return i;};
    body.appendChild(mkI('dc-name','Name (e.g. Main qBit)'));
    body.appendChild(mkI('dc-host','Host (e.g. localhost)'));
    body.appendChild(mkI('dc-port','Port (e.g. 8081)'));
    body.appendChild(mkI('dc-user','Username'));
    body.appendChild(mkI('dc-pass','Password','password'));
    body.appendChild(mkI('dc-cat','Category (e.g. grimmgear)'));
    const btns = el('div','btn-group');
    const testBtn = el('button','btn btn-ghost','Test');
    testBtn.onclick = async () => {
        testBtn.textContent='Testing...';
        const r = await apiPost('/settings/downloadclients/test',{
            name:'test',client_type:typeSelect.value,
            host:document.getElementById('dc-host').value||'localhost',
            port:parseInt(document.getElementById('dc-port').value)||8080,
            username:document.getElementById('dc-user').value,
            password:document.getElementById('dc-pass').value,
        });
        testBtn.textContent=r?.success?'Connected!':'Failed';
        testBtn.className='btn '+(r?.success?'btn-success':'btn-danger');
        toast(r?.message||'Test complete',r?.success?'success':'error');
    };
    btns.appendChild(testBtn);
    const saveBtn = el('button','btn btn-success','Save Client');
    saveBtn.onclick = async () => {
        const r = await apiPost('/settings/downloadclients',{
            name:document.getElementById('dc-name').value||'qBittorrent',
            client_type:typeSelect.value,
            host:document.getElementById('dc-host').value||'localhost',
            port:parseInt(document.getElementById('dc-port').value)||8080,
            username:document.getElementById('dc-user').value,
            password:document.getElementById('dc-pass').value,
            category:document.getElementById('dc-cat').value||'grimmgear',
        });
        if(r?.added){toast('Added: '+r.name,'success');renderSettings();} else toast('Failed','error');
    };
    btns.appendChild(saveBtn);
    body.appendChild(btns);
    panel.appendChild(body); form.appendChild(panel);
    form.scrollIntoView({behavior:'smooth'});
}

// ── Settings: Add Notification Channel Form ───────────────
function showAddNotification() {
    const form = document.getElementById('add-nt-form'); if(!form) return;
    form.textContent='';
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header','Add Notification Channel'));
    const body = el('div','panel-body'); body.style.cssText='display:grid;gap:8px;max-width:500px';
    const typeSelect = el('select','search-input'); typeSelect.id='nt-type';
    [['discord','Discord Webhook'],['telegram','Telegram Bot'],['webhook','Generic Webhook']].forEach(([v,l])=>{
        const o=document.createElement('option');o.value=v;o.textContent=l;typeSelect.appendChild(o);
    });
    typeSelect.onchange = () => {
        document.getElementById('nt-discord-url').parentElement.style.display=typeSelect.value==='discord'?'':'none';
        document.getElementById('nt-tg-token').parentElement.style.display=typeSelect.value==='telegram'?'':'none';
        document.getElementById('nt-tg-chat').parentElement.style.display=typeSelect.value==='telegram'?'':'none';
        document.getElementById('nt-wh-url').parentElement.style.display=typeSelect.value==='webhook'?'':'none';
    };
    body.appendChild(typeSelect);
    const mkI=(id,ph)=>{const w=el('div','');const i=el('input','search-input');i.id=id;i.placeholder=ph;w.appendChild(i);return w;};
    body.appendChild(mkI('nt-name','Channel Name'));
    body.appendChild(mkI('nt-discord-url','Discord Webhook URL'));
    const tgToken=mkI('nt-tg-token','Telegram Bot Token');tgToken.style.display='none';body.appendChild(tgToken);
    const tgChat=mkI('nt-tg-chat','Telegram Chat ID');tgChat.style.display='none';body.appendChild(tgChat);
    const whUrl=mkI('nt-wh-url','Webhook URL');whUrl.style.display='none';body.appendChild(whUrl);
    const saveBtn = el('button','btn btn-success','Add Channel');
    saveBtn.onclick = async () => {
        const type = typeSelect.value;
        const config = {};
        if(type==='discord') config.discord_webhook_url = document.getElementById('nt-discord-url').value;
        if(type==='telegram'){config.telegram_bot_token=document.getElementById('nt-tg-token').value;config.telegram_chat_id=document.getElementById('nt-tg-chat').value;}
        if(type==='webhook') config.webhook_url = document.getElementById('nt-wh-url').value;
        const r = await apiPost('/settings/notifications',{name:document.getElementById('nt-name').value,agent_type:type,config:config});
        if(r?.added){toast('Added: '+r.name,'success');renderSettings();} else toast('Failed','error');
    };
    body.appendChild(saveBtn);
    panel.appendChild(body); form.appendChild(panel);
    form.scrollIntoView({behavior:'smooth'});
}

// ── Settings: Add Quality Profile Form ────────────────────
function showAddQualityProfile() {
    const form = document.getElementById('add-qp-form'); if(!form) return;
    form.textContent='';
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header','Add Quality Profile'));
    const body = el('div','panel-body'); body.style.cssText='display:grid;gap:8px;max-width:500px';
    const mkI=(id,ph)=>{const i=el('input','search-input');i.id=id;i.placeholder=ph;return i;};
    body.appendChild(mkI('qp-name','Profile Name (e.g. HD-1080p)'));
    const langSelect = el('select','search-input'); langSelect.id='qp-lang';
    ['English','Any','French','German','Spanish','Japanese','Korean','Chinese','Portuguese','Italian'].forEach(l=>{
        const o=document.createElement('option');o.value=l;o.textContent=l;langSelect.appendChild(o);
    });
    body.appendChild(langSelect);
    const cutoffSelect = el('select','search-input'); cutoffSelect.id='qp-cutoff';
    ['SDTV','DVD','HDTV-720p','HDTV-1080p','Bluray-720p','Bluray-1080p','Bluray-2160p','Remux-1080p','Remux-2160p'].forEach(q=>{
        const o=document.createElement('option');o.value=q;o.textContent=q;if(q==='Bluray-1080p')o.selected=true;cutoffSelect.appendChild(o);
    });
    body.appendChild(cutoffSelect);
    const upgradeWrap = el('label',''); upgradeWrap.style.cssText='display:flex;align-items:center;gap:8px;font-size:13px';
    const upgradeCb = document.createElement('input'); upgradeCb.type='checkbox'; upgradeCb.id='qp-upgrade'; upgradeCb.checked=true;
    upgradeWrap.appendChild(upgradeCb); upgradeWrap.appendChild(document.createTextNode('Allow upgrades'));
    body.appendChild(upgradeWrap);
    const saveBtn = el('button','btn btn-success','Create Profile');
    saveBtn.onclick = async () => {
        const r = await apiPost('/qualityprofiles',{
            name:document.getElementById('qp-name').value,
            language:langSelect.value,
            cutoff:cutoffSelect.value,
            upgrade_allowed:upgradeCb.checked,
        });
        if(r?.created){toast('Created: '+r.name,'success');renderSettings();} else toast('Failed','error');
    };
    body.appendChild(saveBtn);
    panel.appendChild(body); form.appendChild(panel);
    form.scrollIntoView({behavior:'smooth'});
}

// ── Detail Modal: Movie (from library) ────────────────────
async function showMovieDetail(movieId) {
    const data = await api('/movies/'+movieId+'/detail');
    if(!data){ toast('Failed to load movie details','error'); return; }
    showDetailModal(data, 'movie', true);
}

// ── Detail Modal: Series (from library) ───────────────────
async function showSeriesDetail(seriesId) {
    const data = await api('/series/'+seriesId+'/detail');
    if(!data){ toast('Failed to load series details','error'); return; }
    showDetailModal(data, 'tv', true);
}

// ── Detail Modal: From TMDB search result ─────────────────
async function showTMDBDetail(type, tmdbId) {
    let data;
    if (type === 'movie') {
        data = await api('/search?q=&type=movie'); // We need the direct TMDB endpoint
        // Use the dedicated TMDB fetch
        const resp = await fetch(API+'/search?q=tmdb_'+tmdbId+'&type=movie');
        // Actually, let's fetch from TMDB detail directly via a different approach
        // We'll add the movie first or use the detail endpoint
    }
    // Simpler approach: for TMDB results, show an add dialog
    showTMDBAddModal(type, tmdbId);
}

async function showTMDBAddModal(type, tmdbId) {
    // Fetch TMDB detail directly from our search endpoints
    // We need dedicated endpoints — let's use the add flow
    const overlay = el('div','modal-overlay');
    overlay.onclick = e => { if(e.target===overlay) overlay.remove(); };
    const modal = el('div','modal'); modal.style.maxWidth='500px'; modal.style.padding='24px';
    modal.appendChild(el('div','detail-title','Loading...'));

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Try to fetch detail info
    let detail;
    if (type === 'movie') {
        // Search again with TMDB ID isn't directly available, so use add + detail
        // For now, add directly then show
        modal.textContent = '';
        modal.appendChild(el('div','detail-title','Add to Library?'));
        modal.appendChild(el('div','page-subtitle','TMDB ID: '+tmdbId));

        const actions = el('div','detail-actions');
        const addBtn = el('button','btn btn-success','Add '+(type==='movie'?'Movie':'Series'));
        addBtn.onclick = async () => {
            let r;
            if (type === 'movie') {
                r = await apiPost('/movies', {tmdb_id: tmdbId, monitored: true});
            } else {
                r = await apiPost('/series', {tmdb_id: tmdbId, monitored: true});
            }
            if (r?.added) {
                toast('Added: '+r.title, 'success');
                overlay.remove();
                if (type === 'movie') renderMovies(); else renderTV();
            } else {
                toast('Already in library or failed', 'error');
            }
        };
        actions.appendChild(addBtn);

        const cancelBtn = el('button','btn btn-ghost','Cancel');
        cancelBtn.onclick = () => overlay.remove();
        actions.appendChild(cancelBtn);

        modal.appendChild(actions);
    } else {
        // TV show
        modal.textContent = '';
        modal.appendChild(el('div','detail-title','Add TV Series?'));
        modal.appendChild(el('div','page-subtitle','TMDB ID: '+tmdbId));

        const actions = el('div','detail-actions');
        const addBtn = el('button','btn btn-success','Add Series');
        addBtn.onclick = async () => {
            const r = await apiPost('/series', {tmdb_id: tmdbId, monitored: true});
            if (r?.added) {
                toast('Added: '+r.title+' ('+r.seasons+' seasons)', 'success');
                overlay.remove();
                renderTV();
            } else {
                toast('Already in library or failed', 'error');
            }
        };
        actions.appendChild(addBtn);

        const cancelBtn = el('button','btn btn-ghost','Cancel');
        cancelBtn.onclick = () => overlay.remove();
        actions.appendChild(cancelBtn);

        modal.appendChild(actions);
    }
}

// ── Detail Modal: Full info display ───────────────────────
function showDetailModal(data, type, inLibrary) {
    const overlay = el('div','modal-overlay');
    overlay.onclick = e => { if(e.target===overlay) overlay.remove(); };
    const modal = el('div','modal');

    // Close button
    const closeBtn = el('button','modal-close','\u00D7');
    closeBtn.onclick = () => overlay.remove();
    modal.appendChild(closeBtn);

    // Hero/backdrop
    const hero = el('div','detail-hero');
    if (data.fanart_url) {
        const backdrop = document.createElement('img'); backdrop.className='detail-backdrop'; backdrop.src=data.fanart_url; hero.appendChild(backdrop);
    } else {
        hero.style.height='40px';
    }
    modal.appendChild(hero);

    // Content area
    const contentArea = el('div','detail-content');

    // Poster
    const posterDiv = el('div','detail-poster');
    if (data.poster_url) {
        const posterImg = document.createElement('img'); posterImg.src=data.poster_url; posterDiv.appendChild(posterImg);
    }
    contentArea.appendChild(posterDiv);

    // Info
    const info = el('div','detail-info');
    info.appendChild(el('div','detail-title',data.title+(data.year?' ('+data.year+')':'')));

    // Meta tags
    const meta = el('div','detail-meta');
    if(data.rating) meta.appendChild(el('span','tag tag-yellow','\u2605 '+data.rating.toFixed(1)));
    if(data.runtime) meta.appendChild(el('span','tag tag-blue',data.runtime+' min'));
    if(data.status) meta.appendChild(el('span','tag tag-cyan',data.status));
    if(data.original_language) meta.appendChild(el('span','tag tag-orange',data.original_language.toUpperCase()));
    if(data.has_file) meta.appendChild(el('span','tag tag-green','ON DISK'));
    if(data.genres && Array.isArray(data.genres)) data.genres.forEach(g=>meta.appendChild(el('span','tag tag-blue',g)));
    if(data.number_of_seasons) meta.appendChild(el('span','tag tag-cyan',data.number_of_seasons+' seasons'));
    if(data.number_of_episodes) meta.appendChild(el('span','tag tag-blue',data.number_of_episodes+' episodes'));
    info.appendChild(meta);

    if(data.tagline) info.appendChild(el('div','detail-tagline',data.tagline));
    if(data.overview) info.appendChild(el('div','detail-overview',data.overview));

    // Actions
    const actions = el('div','detail-actions');
    if(data.trailer){
        const trailerBtn = el('a','btn btn-primary','Trailer'); trailerBtn.href=data.trailer; trailerBtn.target='_blank'; actions.appendChild(trailerBtn);
    }
    if(inLibrary && data.title){
        const searchBtn = el('button','btn btn-ghost','Search Releases');
        searchBtn.onclick = () => { overlay.remove(); navigate('search'); setTimeout(()=>{ const inp=document.getElementById('idx-search'); if(inp){inp.value=data.title+(data.year?' '+data.year:''); searchIndexers();} },100); };
        actions.appendChild(searchBtn);
    }
    if(data.monitored !== undefined){
        const monTag = el('span','tag '+(data.monitored?'tag-green':'tag-orange'),data.monitored?'Monitored':'Unmonitored');
        actions.appendChild(monTag);
    }
    info.appendChild(actions);
    contentArea.appendChild(info);
    modal.appendChild(contentArea);

    // Cast section
    if(data.cast?.length > 0){
        const section = el('div','detail-section');
        section.appendChild(el('div','detail-section-title','Cast'));
        const castGrid = el('div','cast-grid');
        data.cast.forEach(c=>{
            const card = el('div','cast-card');
            const img = document.createElement('img');
            img.src=c.profile||''; img.alt=c.name; img.onerror=function(){this.style.background='#444';this.src='';};
            card.appendChild(img);
            card.appendChild(el('div','cast-name',c.name));
            card.appendChild(el('div','cast-char',c.character||''));
            castGrid.appendChild(card);
        });
        section.appendChild(castGrid);
        modal.appendChild(section);
    }

    // Seasons section (for TV)
    if(data.seasons?.length > 0){
        const section = el('div','detail-section');
        section.appendChild(el('div','detail-section-title','Seasons'));
        data.seasons.forEach(s=>{
            if(s.season_number===0 && s.name==='Specials') return; // Skip specials for now
            const item = el('div','season-item');
            const header = el('div','season-header');
            header.textContent = s.name || ('Season '+s.season_number);
            const epCount = el('span','tag tag-blue',(s.episode_count||'?')+' episodes');
            header.appendChild(epCount);
            header.onclick = async () => {
                const epDiv = item.querySelector('.season-episodes');
                if(epDiv.classList.contains('open')){ epDiv.classList.remove('open'); return; }
                epDiv.textContent='Loading...'; epDiv.classList.add('open');
                if(data.id) {
                    const seasonData = await api('/series/'+data.id+'/season/'+s.season_number);
                    epDiv.textContent='';
                    if(seasonData?.episodes){
                        seasonData.episodes.forEach(ep=>{
                            const row = el('div','episode-row');
                            row.appendChild(el('span','ep-num','E'+String(ep.episode_number).padStart(2,'0')));
                            row.appendChild(el('span','',ep.name||'TBA'));
                            if(ep.air_date) row.appendChild(el('span','tag tag-blue',ep.air_date));
                            if(ep.runtime) row.appendChild(el('span','',ep.runtime+'m'));
                            epDiv.appendChild(row);
                        });
                    } else { epDiv.textContent='Could not load episodes'; }
                }
            };
            item.appendChild(header);
            item.appendChild(el('div','season-episodes'));
            section.appendChild(item);
        });
        modal.appendChild(section);
    }

    // Budget/revenue for movies
    if(data.budget || data.revenue){
        const section = el('div','detail-section');
        section.appendChild(el('div','detail-section-title','Box Office'));
        const row = el('div','table-row');
        if(data.budget) row.appendChild(el('span','','Budget: $'+(data.budget/1000000).toFixed(0)+'M'));
        if(data.revenue) { const sp=el('span',''); sp.style.flex='1'; row.appendChild(sp); row.appendChild(el('span','','Revenue: $'+(data.revenue/1000000).toFixed(0)+'M')); }
        section.appendChild(row);
        modal.appendChild(section);
    }

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

// ── Media Player ──────────────────────────────────────────
async function playMedia(streamUrl, title, type) {
    // Close any existing player
    document.querySelectorAll('.player-overlay').forEach(e=>e.remove());

    const overlay = el('div','player-overlay');
    const closeBtn = el('button','player-close','\u00D7');
    closeBtn.onclick = () => overlay.remove();
    overlay.appendChild(closeBtn);
    overlay.appendChild(el('div','player-title',title));

    if(type === 'video') {
        const video = document.createElement('video');
        video.className = 'player-video';
        video.controls = true;
        video.autoplay = true;
        video.crossOrigin = 'anonymous';
        video.src = streamUrl;
        video.onerror = () => toast('Cannot play this format in browser. Try MP4/WebM files.','error');

        // Auto-load subtitles if available
        const token = streamUrl.split('/api/stream/')[1];
        if(token) {
            const subs = await api('/subtitles/local/'+token);
            if(subs?.subtitles?.length > 0) {
                subs.subtitles.forEach((sub, i) => {
                    const track = document.createElement('track');
                    track.kind = 'subtitles';
                    track.label = sub.language.toUpperCase()+' ('+sub.name+')';
                    track.srclang = sub.language;
                    track.src = sub.stream_url;
                    if(i === 0) track.default = true;
                    video.appendChild(track);
                });
            }
        }

        overlay.appendChild(video);
    } else if(type === 'audio') {
        const audioDiv = el('div','player-audio');
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.autoplay = true;
        audio.src = streamUrl;
        audio.style.width = '100%';
        audioDiv.appendChild(audio);
        overlay.appendChild(audioDiv);
    }

    overlay.appendChild(el('div','player-info','Press Escape or click \u00D7 to close. Subtitles auto-loaded if available.'));

    overlay.onclick = e => { if(e.target === overlay) overlay.remove(); };
    document.body.appendChild(overlay);
    overlay.tabIndex = -1;
    overlay.focus();
    overlay.onkeydown = e => { if(e.key === 'Escape') overlay.remove(); };
}

// ── Library: Browsable file view ──────────────────────────
async function browseFolder(path) {
    const data = await api('/library/browse?path='+encodeURIComponent(path));
    if(!data) { toast('Failed to browse folder','error'); return; }

    const sectionDiv = document.getElementById('library-section');
    if(!sectionDiv) return;
    sectionDiv.textContent='';

    const panel = el('div','panel');
    const head = el('div','panel-header');

    // Breadcrumb / back button
    const headContent = el('div',''); headContent.style.cssText='display:flex;align-items:center;gap:8px';
    if(data.parent) {
        const backBtn = el('button','btn btn-ghost btn-xs','\u2190 Back');
        backBtn.onclick = () => browseFolder(data.parent);
        headContent.appendChild(backBtn);
    }
    // Show just the last folder name
    const parts = data.path.replace(/\\/g,'/').split('/');
    headContent.appendChild(el('span','',parts[parts.length-1] || data.path));
    head.appendChild(headContent);
    panel.appendChild(head);

    const body = el('div','panel-body');
    if(data.items.length === 0) {
        body.appendChild(el('div','empty','No media files in this folder'));
    } else {
        data.items.forEach(item => {
            const row = el('div','file-row');

            if(item.type === 'folder') {
                row.appendChild(el('span','file-icon','\uD83D\uDCC1'));
                const name = el('span','file-name',item.name); row.appendChild(name);
                row.appendChild(el('span','file-meta',(item.file_count||0)+' files'));
                row.onclick = () => browseFolder(item.path);
            } else {
                // Playable file
                const icon = item.type==='video' ? '\uD83C\uDFA5' : item.type==='audio' ? '\uD83C\uDFB5' : '\uD83D\uDCD6';
                row.appendChild(el('span','file-icon',icon));
                const name = el('span','file-name',item.name); row.appendChild(name);
                row.appendChild(el('span','file-meta',fmtBytes(item.size||0)));

                if(item.stream_url && (item.type==='video' || item.type==='audio')) {
                    // Show codec badge for video files
                    const ext = item.name.split('.').pop().toLowerCase();
                    if(['mkv','avi','wmv','flv','ts','m2ts'].includes(ext)){
                        row.appendChild(el('span','tag tag-orange','Transcode'));
                    }
                    const playBtn = el('button','play-btn','\u25B6');
                    playBtn.title = 'Play'+(ext==='mkv'?' (auto-transcode)':'');
                    playBtn.onclick = (e) => { e.stopPropagation(); playMedia(item.stream_url, item.name, item.type); };
                    row.appendChild(playBtn);
                }
            }

            body.appendChild(row);
        });
    }
    panel.appendChild(body);
    sectionDiv.appendChild(panel);
    sectionDiv.scrollIntoView({behavior:'smooth',block:'start'});
}

// ── Nav count badges ──────────────────────────────────────
function updateNavCount(page, count) {
    const link = document.querySelector(`.nav-link[data-page="${page}"]`);
    if(!link) return;
    let badge = link.querySelector('.nav-count');
    if(count > 0){
        if(!badge){ badge = el('span','nav-count'); link.appendChild(badge); }
        badge.textContent = count;
    } else if(badge) badge.remove();
}

// ── Speed ticker ──────────────────────────────────────────
setInterval(async()=>{
    const s=await api('/downloads/speed');
    if(s) document.getElementById('dl-speed-mini').textContent=fmtSpeed(s.dl_speed);
}, 5000);

// ── Hash-based routing ────────────────────────────────────
function initFromHash() {
    const hash = window.location.hash.replace('#','');
    if(hash && ['dashboard','movies','tv','search','downloads','library','requests','indexers','settings'].includes(hash)){
        navigate(hash);
    } else {
        navigate('dashboard');
    }
}

// ── Mobile sidebar ────────────────────────────────────────
function initMobile() {
    const hamburger = document.querySelector('.hamburger');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.mobile-overlay');
    if(hamburger){
        hamburger.onclick = () => {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        };
    }
    if(overlay){
        overlay.onclick = () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        };
    }
}

// ── First-Run Setup Wizard ────────────────────────────────
async function checkFirstRun() {
    const status = await api('/setup/status');
    if(status?.needs_setup) {
        showSetupWizard();
        return true;
    }
    return false;
}

async function showSetupWizard() {
    content.textContent='';
    // Hide sidebar during setup
    document.getElementById('sidebar').style.display='none';
    document.querySelector('.hamburger').style.display='none';

    const wizard = el('div',''); wizard.style.cssText='max-width:500px;margin:40px auto;padding:0 20px';

    // Header
    const header = el('div',''); header.style.cssText='text-align:center;margin-bottom:32px';
    const logo = el('div','brand-icon'); logo.style.cssText='width:60px;height:60px;font-size:28px;margin:0 auto 12px;border-radius:12px;display:flex;align-items:center;justify-content:center';
    logo.textContent='G'; header.appendChild(logo);
    header.appendChild(el('div','page-title','Welcome to Mediarr'));
    header.appendChild(el('div','page-subtitle','One system. Every media type. Let\'s set it up.'));
    wizard.appendChild(header);

    // Step 1: Create admin account
    const step1 = el('div','panel');
    step1.appendChild(el('div','panel-header','Step 1: Create Admin Account'));
    const body1 = el('div','panel-body'); body1.style.cssText='display:grid;gap:10px';
    const mkInput=(id,ph,type)=>{ const i=el('input','search-input'); i.id=id; i.placeholder=ph; if(type)i.type=type; return i; };
    body1.appendChild(mkInput('setup-user','Username'));
    body1.appendChild(mkInput('setup-pass','Password','password'));
    body1.appendChild(mkInput('setup-email','Email (optional)','email'));
    const createBtn = el('button','btn btn-primary','Create Account');
    createBtn.onclick = async () => {
        const user = document.getElementById('setup-user').value;
        const pass = document.getElementById('setup-pass').value;
        if(!user||!pass){ toast('Username and password required','error'); return; }
        const r = await apiPost('/auth/register',{username:user,password:pass,email:document.getElementById('setup-email').value});
        if(r?.registered){
            toast('Admin account created: '+r.username,'success');
            createBtn.textContent='Done!'; createBtn.className='btn btn-success'; createBtn.disabled=true;
            step2.style.opacity='1'; step2.style.pointerEvents='auto';
        } else toast('Failed to create account','error');
    };
    body1.appendChild(createBtn);
    step1.appendChild(body1); wizard.appendChild(step1);

    // Step 2: Import indexers
    const step2 = el('div','panel'); step2.style.cssText='opacity:0.5;pointer-events:none;margin-top:12px';
    step2.appendChild(el('div','panel-header','Step 2: Configure Indexers'));
    const body2 = el('div','panel-body');
    body2.appendChild(el('div','page-subtitle','Import indexers from Prowlarr (auto-detected) or add manually later.'));
    const importBtn = el('button','btn btn-primary','Import from Prowlarr');
    importBtn.onclick = async () => {
        importBtn.textContent='Importing...';
        const r = await apiPost('/indexers/import-from-prowlarr');
        if(r?.imported > 0){
            toast('Imported '+r.imported+' indexers!','success');
            importBtn.textContent=r.imported+' imported!'; importBtn.className='btn btn-success'; importBtn.disabled=true;
        } else {
            toast('No Prowlarr found. You can add indexers later from Settings.','');
            importBtn.textContent='Skip (add later)'; importBtn.className='btn btn-ghost';
        }
        step3.style.opacity='1'; step3.style.pointerEvents='auto';
    };
    const skipIdx = el('button','btn btn-ghost','Skip');
    skipIdx.style.marginLeft='8px';
    skipIdx.onclick = () => { step3.style.opacity='1'; step3.style.pointerEvents='auto'; };
    const btnRow2 = el('div','btn-group'); btnRow2.appendChild(importBtn); btnRow2.appendChild(skipIdx);
    body2.appendChild(btnRow2);
    step2.appendChild(body2); wizard.appendChild(step2);

    // Step 3: Verify media paths
    const step3 = el('div','panel'); step3.style.cssText='opacity:0.5;pointer-events:none;margin-top:12px';
    step3.appendChild(el('div','panel-header','Step 3: Media Library'));
    const body3 = el('div','panel-body');
    const stats = await api('/library/stats');
    if(stats){
        let totalFiles = 0;
        for(const [key,info] of Object.entries(stats)){
            totalFiles += info.files||0;
            const row = el('div','table-row');
            row.appendChild(el('span','',key.charAt(0).toUpperCase()+key.slice(1)));
            const spacer=el('span',''); spacer.style.flex='1'; row.appendChild(spacer);
            row.appendChild(el('span','tag '+(info.files>0?'tag-green':'tag-orange'),info.files+' files'));
            body3.appendChild(row);
        }
        if(totalFiles>0) body3.appendChild(el('div','page-subtitle','Media found! Your library is ready.'));
        else body3.appendChild(el('div','page-subtitle','No media found yet. Add files to D:\\Media or change the path in settings.'));
    }
    const finishBtn = el('button','btn btn-success','Start Using Mediarr');
    finishBtn.style.marginTop='12px';
    finishBtn.onclick = () => {
        document.getElementById('sidebar').style.display='';
        document.querySelector('.hamburger').style.display='';
        navigate('dashboard');
    };
    body3.appendChild(finishBtn);
    step3.appendChild(body3); wizard.appendChild(step3);

    content.appendChild(wizard);
}

// ── Init ──────────────────────────────────────────────────
async function init() {
    initMobile();
    const isFirstRun = await checkFirstRun();
    if(!isFirstRun) {
        initFromHash();
    }
}
init();
window.onhashchange = initFromHash;
