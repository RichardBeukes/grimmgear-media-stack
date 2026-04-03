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
    const routes = {dashboard:renderDashboard,movies:renderMovies,tv:renderTV,search:renderSearch,downloads:renderDownloads,library:renderLibrary,indexers:renderIndexers,settings:renderSettings};
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
    const data=await api('/search/indexers?q='+encodeURIComponent(q));
    rd.textContent='';
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

        // Show files on click
        if(item.files?.length > 0){
            row.onclick = () => {
                const existing = row.nextElementSibling;
                if(existing?.classList?.contains('lib-files')){ existing.remove(); return; }
                const filesDiv = el('div','lib-files');
                filesDiv.style.cssText='padding:4px 0 8px 30px;font-size:11px;color:var(--text-dim)';
                item.files.forEach(f => { filesDiv.appendChild(el('div','','\u2022 '+f)); });
                row.after(filesDiv);
            };
        }

        body.appendChild(row);
    });

    panel.appendChild(body);
    sectionDiv.appendChild(panel);

    // Scroll to section
    sectionDiv.scrollIntoView({behavior:'smooth',block:'start'});
}

// ── Indexers ──────────────────────────────────────────────
async function renderIndexers() {
    content.textContent='';
    content.appendChild(el('div','page-title','Indexers'));

    const panel = el('div','panel');
    const head = el('div','panel-header');
    head.appendChild(el('span','','Indexers'));
    const addBtn = el('button','btn btn-primary btn-sm','+ Add Indexer'); addBtn.onclick=showAddIndexer; head.appendChild(addBtn);
    panel.appendChild(head);
    const body = el('div','panel-body');
    const indexers = await api('/indexers');
    if(indexers?.length>0){
        indexers.forEach(i=>{
            const row = el('div','table-row');
            const tag = el('span','tag '+(i.enabled?'tag-green':'tag-red')); tag.textContent=i.enabled?'Enabled':'Disabled'; row.appendChild(tag);
            const nm = el('span',''); nm.style.cssText='flex:1;font-weight:600'; nm.textContent=i.name; row.appendChild(nm);
            row.appendChild(el('span','tag tag-blue',i.type));
            if(i.use_flaresolverr) row.appendChild(el('span','tag tag-orange','CF'));
            const del = el('button','btn btn-danger btn-xs','Remove'); del.onclick=()=>{if(confirm('Remove '+i.name+'?'))apiDelete('/indexers/'+i.id).then(()=>renderIndexers());}; row.appendChild(del);
            body.appendChild(row);
        });
    } else { body.appendChild(el('div','empty','No indexers configured. Add some to search for releases.')); }
    panel.appendChild(body); content.appendChild(panel);
    content.appendChild(el('div','')).id='add-indexer-form';
}

function showAddIndexer(){
    const form=document.getElementById('add-indexer-form'); form.textContent='';
    const panel = el('div','panel');
    panel.appendChild(el('div','panel-header','Add Indexer'));
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
    panel.appendChild(body); form.appendChild(panel);
}

// ── Settings ──────────────────────────────────────────────
async function renderSettings() {
    content.textContent='';
    content.appendChild(el('div','page-title','Settings'));

    const [status,modules,health,scheduler]=await Promise.all([api('/system/status'),api('/modules'),api('/system/health'),api('/scheduler/status')]);

    // System info
    const sysPanel = el('div','panel');
    sysPanel.appendChild(el('div','panel-header','System'));
    const sysBody = el('div','panel-body');
    if(status){
        [['Version',status.version],['Database',status.database],['Media Root',status.media_root],['Downloads',status.download_dir],['Media Server',status.media_server],
         ['qBittorrent',status.download_client?(status.download_client.version+' ('+(status.download_client.connected?'connected':'offline')+')'):'N/A']
        ].forEach(([k,v])=>{
            const row = el('div','table-row');
            row.appendChild(el('span','',k)); const spacer=el('span',''); spacer.style.flex='1'; row.appendChild(spacer);
            const val=el('span','',String(v)); val.style.color='var(--text-bright)'; row.appendChild(val);
            sysBody.appendChild(row);
        });
    }
    sysPanel.appendChild(sysBody); content.appendChild(sysPanel);

    // Scheduler
    const schedPanel = el('div','panel');
    schedPanel.appendChild(el('div','panel-header','Background Scheduler'));
    const schedBody = el('div','panel-body');
    if(scheduler){
        [['Running',scheduler.running?'Yes':'No'],['Tasks',scheduler.tasks?.join(', ')||'none'],['Last Import Scan',scheduler.last_import_scan],['Last RSS Sync',scheduler.last_rss_sync]
        ].forEach(([k,v])=>{
            const row = el('div','table-row');
            row.appendChild(el('span','',k)); const spacer=el('span',''); spacer.style.flex='1'; row.appendChild(spacer);
            const val=el('span','',v); val.style.color='var(--text-bright)'; row.appendChild(val);
            schedBody.appendChild(row);
        });
    }
    schedPanel.appendChild(schedBody); content.appendChild(schedPanel);

    // Plex section
    const plexPanel = el('div','panel');
    const plexHead = el('div','panel-header');
    plexHead.appendChild(el('span','','Plex'));
    const scanBtn = el('button','btn btn-primary btn-sm','Scan Library');
    scanBtn.onclick=async()=>{ const r=await apiPost('/plex/scan'); toast(r?.triggered?'Plex scan triggered':'Plex: '+(r?.reason||'not configured'), r?.triggered?'success':'error'); };
    plexHead.appendChild(scanBtn);
    plexPanel.appendChild(plexHead);
    const plexBody = el('div','panel-body');
    plexBody.appendChild(el('div','',status?.media_server==='plex'?'Plex connected':'Configure Plex: set GG_MEDIA_SERVER_TYPE=plex, GG_MEDIA_SERVER_URL, GG_MEDIA_SERVER_TOKEN'));
    plexPanel.appendChild(plexBody); content.appendChild(plexPanel);

    // Modules
    const modPanel = el('div','panel');
    modPanel.appendChild(el('div','panel-header','Modules'));
    const modBody = el('div','panel-body');
    if(modules){
        Object.entries(modules).forEach(([name,mod])=>{
            const row = el('div','table-row');
            const info = el('span',''); info.style.flex='1';
            info.appendChild(el('strong','',mod.display_name));
            info.appendChild(document.createElement('br'));
            const desc = el('span','',mod.description); desc.style.cssText='font-size:11px;color:var(--text-dim)'; info.appendChild(desc);
            row.appendChild(info);
            const label = el('label',''); label.style.cssText='cursor:pointer;display:flex;align-items:center;gap:6px';
            const cb = document.createElement('input'); cb.type='checkbox'; cb.checked=mod.enabled;
            cb.onchange=async function(){ await apiPost('/modules/'+name+'/'+(this.checked?'enable':'disable')); toast(mod.display_name+' '+(this.checked?'enabled':'disabled'),'success'); };
            label.appendChild(cb);
            const statusTag = el('span','tag '+(mod.enabled?'tag-green':'tag-orange'),mod.enabled?'ON':'OFF'); label.appendChild(statusTag);
            row.appendChild(label);
            modBody.appendChild(row);
        });
    }
    modPanel.appendChild(modBody); content.appendChild(modPanel);
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
    if(hash && ['dashboard','movies','tv','search','downloads','library','indexers','settings'].includes(hash)){
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

// ── Init ──────────────────────────────────────────────────
initMobile();
initFromHash();
window.onhashchange = initFromHash;
