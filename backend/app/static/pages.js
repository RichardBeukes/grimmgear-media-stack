// GrimmGear Mediarr — Calendar, Blocklist, System, Music, Books, Comics Pages
// Loaded after app.js

// ── Shared: Media Tab Renderer (On Disk / Library / Upcoming / Popular / Search) ──
async function renderMediaTab(container, mediaType, tab) {
    container.textContent = '';
    var typeLabels = {movie:'Movies',tv:'TV Shows',music:'Music',books:'Books',comics:'Comics'};
    var searchTypes = {movie:'movie',tv:'tv'};

    if (tab === 'On Disk') {
        // Refresh button
        var bar = el('div','filter-bar');
        var refreshBtn = el('button','btn btn-sm','Refresh Scan');
        refreshBtn.onclick = function() { renderMediaTab(container, mediaType, 'On Disk'); toast('Rescanning...'); };
        bar.appendChild(refreshBtn);
        var autoLabel = el('span','text-dim','Auto-refresh: 5 min');
        autoLabel.style.marginLeft = '12px';
        bar.appendChild(autoLabel);
        container.appendChild(bar);

        var data = await api('/ondisk/' + mediaType);
        if (!data || !data.folders || !data.folders.length) {
            var empty = el('div','panel');
            empty.appendChild(el('div','panel-body'));
            empty.lastChild.appendChild(el('p','text-dim','No ' + (typeLabels[mediaType]||mediaType) + ' files found at ' + (data && data.path || 'unknown path')));
            container.appendChild(empty);
            return;
        }

        // Stats bar
        var statsDiv = el('div','stat-row');
        function mkStat(label, value, sub, color) {
            var c = el('div','stat-card');
            var bar2 = el('div','accent-bar'); bar2.style.background = color; c.appendChild(bar2);
            c.appendChild(el('div','stat-label',label));
            c.appendChild(el('div','stat-value',String(value)));
            c.appendChild(el('div','stat-sub',sub));
            return c;
        }
        statsDiv.appendChild(mkStat('Folders', data.folders.length, '', 'var(--cyan)'));
        statsDiv.appendChild(mkStat('Files', data.total_files, fmtBytes(data.total_size), 'var(--green)'));
        statsDiv.appendChild(mkStat('Path', '', data.path, 'var(--yellow)'));
        container.appendChild(statsDiv);

        // Folder list
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header',(typeLabels[mediaType]||mediaType) + ' on Disk (' + data.total_files + ' files)'));
        var body = el('div','panel-body');
        body.style.maxHeight = '500px';
        body.style.overflow = 'auto';
        for (var i = 0; i < data.folders.length; i++) {
            var f = data.folders[i];
            var row = el('div','table-row');
            row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)';
            row.appendChild(el('span','',f.folder));
            var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
            row.appendChild(el('span','tag tag-cyan', f.file_count + ' files'));
            row.appendChild(el('span','text-dim', fmtBytes(f.size)));
            body.appendChild(row);
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Library') {
        // DB library (added/monitored items)
        var libUrl = mediaType === 'movie' ? '/movies' : mediaType === 'tv' ? '/series' : '/' + mediaType + '/library';
        var data = await api(libUrl);
        var items = Array.isArray(data) ? data : (data && data.items ? data.items : data && data.books ? data.books : []);

        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Library (' + items.length + ' items)'));
        var body = el('div','panel-body');
        if (items.length) {
            var grid = el('div','card-grid');
            for (var i = 0; i < Math.min(items.length, 50); i++) {
                var m = items[i];
                var card = mkMediaCard(m.title || m.name || '', m.year || '', m.poster_url || '', m.has_file || false);
                if (mediaType === 'movie' && m.id) {
                    (function(id) { card.onclick = function() { showMovieDetail(id); }; })(m.id);
                } else if (mediaType === 'tv' && m.id) {
                    (function(id) { card.onclick = function() { showSeriesDetail(id); }; })(m.id);
                }
                grid.appendChild(card);
            }
            body.appendChild(grid);
        } else {
            body.appendChild(el('p','text-dim','No items in library. Search and add ' + (typeLabels[mediaType]||mediaType) + '.'));
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Upcoming') {
        container.appendChild(el('p','text-dim','Loading upcoming releases...'));
        var data = await api('/upcoming/' + mediaType);
        container.textContent = '';
        if (!data || !data.items || !data.items.length) {
            container.appendChild(el('p','text-dim','No upcoming ' + (typeLabels[mediaType]||mediaType) + ' found.'));
            return;
        }
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Upcoming ' + (typeLabels[mediaType]||mediaType) + ' (' + data.items.length + ')'));
        var body = el('div','panel-body');
        var grid = el('div','card-grid');
        for (var i = 0; i < data.items.length; i++) {
            var m = data.items[i];
            var subtitle = (m.date || '') + (m.artist ? ' \u2014 ' + m.artist : '') + (m.source ? ' (' + m.source + ')' : '');
            var card = mkMediaCard(m.title || '', subtitle, m.poster_url || m.cover_url || '', false);
            grid.appendChild(card);
        }
        body.appendChild(grid);
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Popular') {
        container.appendChild(el('p','text-dim','Loading popular...'));
        var data = await api('/popular/' + mediaType);
        container.textContent = '';
        if (!data || !data.items || !data.items.length) {
            container.appendChild(el('p','text-dim','No popular ' + (typeLabels[mediaType]||mediaType) + ' found.'));
            return;
        }
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Popular ' + (typeLabels[mediaType]||mediaType) + ' (' + data.items.length + ')'));
        var body = el('div','panel-body');
        var grid = el('div','card-grid');
        for (var i = 0; i < data.items.length; i++) {
            var m = data.items[i];
            var subtitle = (m.date || '') + (m.rating ? ' \u2605' + m.rating.toFixed(1) : '') + (m.source ? ' (' + m.source + ')' : '');
            var card = mkMediaCard(m.title || '', subtitle, m.poster_url || '', false);
            if (m.tmdb_id && (mediaType === 'movie' || mediaType === 'tv')) {
                (function(type, id) { card.onclick = function() { showTMDBDetail(type, id); }; })(mediaType, m.tmdb_id);
            }
            grid.appendChild(card);
        }
        body.appendChild(grid);
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Search') {
        var searchBar = el('div','search-box');
        var searchType = searchTypes[mediaType] || 'multi';
        var input = el('input','search-input');
        input.placeholder = 'Search for ' + (typeLabels[mediaType]||mediaType) + '...';
        input.style.flex = '1';
        var btn = el('button','btn btn-primary','Search');
        searchBar.appendChild(input);
        searchBar.appendChild(btn);
        container.appendChild(searchBar);
        var resultsDiv = el('div','');
        container.appendChild(resultsDiv);

        function doSearch() {
            var q = input.value.trim();
            if (!q) return;
            resultsDiv.textContent = 'Searching...';
            api('/search?q=' + encodeURIComponent(q) + '&type=' + searchType).then(function(data) {
                resultsDiv.textContent = '';
                if (!data || !data.length) { resultsDiv.appendChild(el('p','text-dim','No results.')); return; }
                var grid = el('div','card-grid');
                for (var i = 0; i < Math.min(data.length, 20); i++) {
                    var m = data[i];
                    var card = mkMediaCard(m.title || m.name || '', (m.year||'') + (m.rating ? ' \u2605' + m.rating.toFixed(1) : ''), m.poster_url || '', false);
                    if (m.tmdb_id) {
                        (function(type, id) { card.onclick = function() { showTMDBDetail(type, id); }; })(mediaType, m.tmdb_id);
                    }
                    grid.appendChild(card);
                }
                resultsDiv.appendChild(grid);
                resultsDiv.appendChild(el('div','page-subtitle','Click to see details and add'));
            });
        }
        btn.onclick = doSearch;
        input.onkeydown = function(e) { if (e.key === 'Enter') doSearch(); };
    }
}

// ── Calendar ─────────────────────────────────────────────
var _calViewDate = new Date();
var _calView = 'month';

async function renderCalendar() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Calendar'));

    var typeColors = {movie:'var(--yellow)',tv:'var(--cyan)',tv_episode:'var(--cyan)',album:'var(--green)',music:'var(--green)',book:'var(--orange)',comic:'var(--red)'};
    var tagColors = {movie:'tag-yellow',tv:'tag-cyan',tv_episode:'tag-cyan',album:'tag-green',music:'tag-green',book:'tag-orange',comic:'tag-red'};

    // View switcher + month nav
    var nav = el('div','filter-bar');
    nav.style.cssText = 'display:flex;align-items:center;gap:8px;flex-wrap:wrap';
    var prevBtn = el('button','btn btn-sm','\u25C0');
    var nextBtn = el('button','btn btn-sm','\u25B6');
    var todayBtn = el('button','btn btn-sm','Today');
    var monthLabel = el('span','page-subtitle','');
    monthLabel.style.cssText = 'min-width:180px;text-align:center;font-weight:600;font-size:16px';
    var spacer = el('span',''); spacer.style.flex = '1';
    var viewBtns = el('div','btn-group');
    var btnMonth = el('button','btn btn-sm' + (_calView==='month'?' btn-primary':''),'Month');
    var btnWeek = el('button','btn btn-sm' + (_calView==='week'?' btn-primary':''),'Week');
    var btnYear = el('button','btn btn-sm' + (_calView==='year'?' btn-primary':''),'Year');
    viewBtns.appendChild(btnMonth); viewBtns.appendChild(btnWeek); viewBtns.appendChild(btnYear);
    nav.appendChild(prevBtn); nav.appendChild(todayBtn); nav.appendChild(nextBtn);
    nav.appendChild(monthLabel); nav.appendChild(spacer); nav.appendChild(viewBtns);
    content.appendChild(nav);

    var calArea = el('div','');
    content.appendChild(calArea);

    // Upcoming list below calendar
    // No trending/upcoming panel — calendar IS the upcoming view

    var data = await api('/calendar/smart');
    var events = (data && data.events) || [];
    var grouped = {};
    for (var i = 0; i < events.length; i++) {
        var d = events[i].date || '';
        if (!grouped[d]) grouped[d] = [];
        grouped[d].push(events[i]);
    }

    function fmtMonthYear(dt) {
        var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
        return months[dt.getMonth()] + ' ' + dt.getFullYear();
    }

    function drawMonth() {
        calArea.textContent = '';
        monthLabel.textContent = fmtMonthYear(_calViewDate);
        var grid = el('div','');
        grid.style.cssText = 'display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-top:8px';
        var dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
        for (var i = 0; i < 7; i++) {
            var hdr = el('div','',dayNames[i]);
            hdr.style.cssText = 'text-align:center;padding:6px;font-weight:700;color:var(--text-dim);font-size:12px;background:var(--bg-secondary);border-radius:4px';
            grid.appendChild(hdr);
        }
        var ms = new Date(_calViewDate.getFullYear(), _calViewDate.getMonth(), 1);
        var me = new Date(_calViewDate.getFullYear(), _calViewDate.getMonth() + 1, 0);
        var today = new Date().toISOString().split('T')[0];
        for (var i = 0; i < ms.getDay(); i++) { var e = el('div',''); e.style.background = 'var(--bg-primary)'; grid.appendChild(e); }
        for (var d = 1; d <= me.getDate(); d++) {
            var ds = _calViewDate.getFullYear()+'-'+String(_calViewDate.getMonth()+1).padStart(2,'0')+'-'+String(d).padStart(2,'0');
            var cell = el('div','');
            cell.style.cssText = 'min-height:80px;padding:4px;background:var(--card-bg);border-radius:4px;font-size:12px;border:1px solid var(--border)';
            if (ds === today) cell.style.border = '2px solid var(--accent)';
            var dn = el('div','',String(d));
            dn.style.cssText = 'font-weight:700;margin-bottom:2px';
            if (ds === today) dn.style.color = 'var(--accent)';
            cell.appendChild(dn);
            var dayEvs = grouped[ds] || [];
            for (var j = 0; j < Math.min(dayEvs.length, 4); j++) {
                var dot = el('div','',dayEvs[j].title.substring(0,25));
                dot.style.cssText = 'font-size:9px;padding:1px 3px;margin-top:1px;border-radius:2px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;color:#000;background:' + (typeColors[dayEvs[j].type]||'var(--cyan)');
                cell.appendChild(dot);
            }
            if (dayEvs.length > 4) cell.appendChild(el('div','text-dim','+' + (dayEvs.length-4) + ' more'));
            grid.appendChild(cell);
        }
        calArea.appendChild(grid);
    }

    function drawWeek() {
        calArea.textContent = '';
        var start = new Date(_calViewDate);
        start.setDate(start.getDate() - start.getDay());
        var end = new Date(start); end.setDate(end.getDate() + 6);
        monthLabel.textContent = 'Week of ' + start.toLocaleDateString() + ' \u2013 ' + end.toLocaleDateString();
        var grid = el('div','');
        grid.style.cssText = 'display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin-top:8px';
        var today = new Date().toISOString().split('T')[0];
        for (var i = 0; i < 7; i++) {
            var day = new Date(start); day.setDate(day.getDate() + i);
            var ds = day.toISOString().split('T')[0];
            var dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
            var cell = el('div','');
            cell.style.cssText = 'min-height:200px;padding:6px;background:var(--card-bg);border-radius:4px;border:1px solid var(--border)';
            if (ds === today) cell.style.border = '2px solid var(--accent)';
            var hdr = el('div','',dayNames[i] + ' ' + day.getDate());
            hdr.style.cssText = 'font-weight:700;font-size:13px;margin-bottom:4px';
            if (ds === today) hdr.style.color = 'var(--accent)';
            cell.appendChild(hdr);
            var dayEvs = grouped[ds] || [];
            for (var j = 0; j < dayEvs.length; j++) {
                var item = el('div','',dayEvs[j].title);
                item.style.cssText = 'font-size:11px;padding:2px 4px;margin-top:2px;border-radius:3px;color:#000;background:' + (typeColors[dayEvs[j].type]||'var(--cyan)');
                cell.appendChild(item);
            }
            if (!dayEvs.length) cell.appendChild(el('div','text-dim','No events'));
            grid.appendChild(cell);
        }
        calArea.appendChild(grid);
    }

    function drawYear() {
        calArea.textContent = '';
        monthLabel.textContent = String(_calViewDate.getFullYear());
        var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
        var today = new Date();
        for (var m = 0; m < 12; m++) {
            // Collect events for this month
            var mDays = new Date(_calViewDate.getFullYear(), m + 1, 0).getDate();
            var monthEvents = [];
            for (var d = 1; d <= mDays; d++) {
                var ds = _calViewDate.getFullYear()+'-'+String(m+1).padStart(2,'0')+'-'+String(d).padStart(2,'0');
                var dayEvs = grouped[ds] || [];
                for (var j = 0; j < dayEvs.length; j++) monthEvents.push(dayEvs[j]);
            }
            // Only show months that have events, or current month
            var isCurrent = (m === today.getMonth() && _calViewDate.getFullYear() === today.getFullYear());
            if (!monthEvents.length && !isCurrent) continue;

            var mPanel = el('div','panel');
            mPanel.style.marginTop = '8px';
            var mHead = el('div','panel-header', months[m] + (monthEvents.length ? ' (' + monthEvents.length + ')' : ''));
            if (isCurrent) mHead.style.color = 'var(--accent)';
            mHead.style.cursor = 'pointer';
            (function(month) { mHead.onclick = function() { _calViewDate = new Date(_calViewDate.getFullYear(), month, 1); _calView = 'month'; draw(); }; })(m);
            mPanel.appendChild(mHead);
            var mBody = el('div','panel-body');
            if (monthEvents.length) {
                for (var j = 0; j < monthEvents.length; j++) {
                    var ev = monthEvents[j];
                    var row = el('div','table-row');
                    row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--border)';
                    row.appendChild(el('span','tag ' + (tagColors[ev.type]||''), ev.type));
                    var dateSpan = el('span','text-dim', ev.date ? ev.date.substring(5) : '');
                    dateSpan.style.minWidth = '50px';
                    row.appendChild(dateSpan);
                    var t = el('span','',ev.title); t.style.flex = '1'; row.appendChild(t);
                    if (ev.source) row.appendChild(el('span','text-dim',ev.source));
                    mBody.appendChild(row);
                }
            } else {
                mBody.appendChild(el('p','text-dim','No releases this month'));
            }
            mPanel.appendChild(mBody);
            calArea.appendChild(mPanel);
        }
    }

    function drawUpcoming() { /* removed — calendar is the upcoming view */ }

    function draw() {
        btnMonth.className = 'btn btn-sm' + (_calView==='month'?' btn-primary':'');
        btnWeek.className = 'btn btn-sm' + (_calView==='week'?' btn-primary':'');
        btnYear.className = 'btn btn-sm' + (_calView==='year'?' btn-primary':'');
        if (_calView === 'month') drawMonth();
        else if (_calView === 'week') drawWeek();
        else drawYear();
        drawUpcoming();
    }

    prevBtn.onclick = function() {
        if (_calView === 'month') _calViewDate.setMonth(_calViewDate.getMonth() - 1);
        else if (_calView === 'week') _calViewDate.setDate(_calViewDate.getDate() - 7);
        else _calViewDate.setFullYear(_calViewDate.getFullYear() - 1);
        draw();
    };
    nextBtn.onclick = function() {
        if (_calView === 'month') _calViewDate.setMonth(_calViewDate.getMonth() + 1);
        else if (_calView === 'week') _calViewDate.setDate(_calViewDate.getDate() + 7);
        else _calViewDate.setFullYear(_calViewDate.getFullYear() + 1);
        draw();
    };
    todayBtn.onclick = function() { _calViewDate = new Date(); draw(); };
    btnMonth.onclick = function() { _calView = 'month'; draw(); };
    btnWeek.onclick = function() { _calView = 'week'; draw(); };
    btnYear.onclick = function() { _calView = 'year'; draw(); };

    draw();
}

// ── Blocklist ────────────────────────────────────────────
async function renderBlocklist() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Blocklist'));
    content.appendChild(el('p','page-subtitle','Blocked releases that will never be grabbed again'));

    const bar = el('div','filter-bar');
    const addBtn = el('button','btn btn-sm','+ Add to Blocklist');
    const clearBtn = el('button','btn btn-sm btn-danger','Clear All');
    bar.appendChild(addBtn);
    bar.appendChild(clearBtn);
    content.appendChild(bar);

    const data = await api('/blocklist');
    const table = el('div','panel');
    table.appendChild(el('div','panel-header','Blocked Releases (' + (data && data.total || 0) + ')'));
    const body = el('div','panel-body');

    if (!data || !data.items || !data.items.length) {
        body.appendChild(el('p','text-dim','No blocked releases. Items are added when you reject a download or manually block a release.'));
    } else {
        for (const item of data.items) {
            const row = el('div','table-row');
            row.style.display = 'flex';
            row.style.alignItems = 'center';
            row.style.gap = '8px';
            row.style.padding = '8px 0';
            row.style.borderBottom = '1px solid var(--border)';

            const info = el('div','');
            info.style.flex = '1';
            info.appendChild(el('div','',item.title));
            const meta = el('div','text-dim');
            meta.style.fontSize = '12px';
            meta.textContent = (item.indexer || 'Unknown') + ' | ' + item.protocol + ' | ' + item.reason + ' | ' + (item.date ? new Date(item.date).toLocaleDateString() : '');
            info.appendChild(meta);
            row.appendChild(info);
            row.appendChild(el('span','tag tag-' + (item.media_type === 'movie' ? 'yellow' : 'cyan'), item.media_type));

            const delBtn = el('button','btn btn-sm btn-danger','Remove');
            (function(id) { delBtn.onclick = async function() { await apiDelete('/blocklist/' + id); renderBlocklist(); }; })(item.id);
            row.appendChild(delBtn);
            body.appendChild(row);
        }
    }
    table.appendChild(body);
    content.appendChild(table);

    addBtn.onclick = function() {
        const modal = el('div','modal-overlay');
        modal.onclick = function(e) { if (e.target === modal) modal.remove(); };
        const box = el('div','modal-box');
        box.appendChild(el('h3','','Add to Blocklist'));
        const form = el('div','form-grid');

        form.appendChild(el('label','','Release Title'));
        const titleIn = el('input','input'); titleIn.placeholder = 'Release.Name.2024.1080p.BluRay'; form.appendChild(titleIn);
        form.appendChild(el('label','','Indexer'));
        const idxIn = el('input','input'); idxIn.placeholder = '1337x'; form.appendChild(idxIn);
        form.appendChild(el('label','','Media Type'));
        const typeSelect = el('select','input');
        ['movie','tv','music','book'].forEach(function(t) { const o = el('option','',t); o.value = t; typeSelect.appendChild(o); });
        form.appendChild(typeSelect);
        form.appendChild(el('label','','Reason'));
        const reasonIn = el('input','input'); reasonIn.value = 'manual'; form.appendChild(reasonIn);

        box.appendChild(form);
        const saveBtn = el('button','btn btn-success','Add');
        saveBtn.onclick = async function() {
            await apiPost('/blocklist', {
                title: titleIn.value, indexer: idxIn.value,
                media_type: typeSelect.value, reason: reasonIn.value,
            });
            modal.remove();
            renderBlocklist();
        };
        box.appendChild(saveBtn);
        modal.appendChild(box);
        document.body.appendChild(modal);
    };

    clearBtn.onclick = async function() {
        if (confirm('Clear ALL blocked releases?')) {
            await apiDelete('/blocklist/bulk');
            renderBlocklist();
        }
    };
}

// ── System ───────────────────────────────────────────────
async function renderSystem() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','System'));

    const tabs = el('div','settings-tabs');
    const tabNames = ['Status','Tasks','Health','Events','Logs','Backups','Tags','Custom Formats','Import Lists','Naming'];
    var activeTab = 'Status';
    const tabContent = el('div','tab-content');

    for (var i = 0; i < tabNames.length; i++) {
        (function(t) {
            var btn = el('button','settings-tab' + (t === activeTab ? ' active' : ''), t);
            btn.onclick = function() {
                activeTab = t;
                tabs.querySelectorAll('.settings-tab').forEach(function(b) { b.classList.toggle('active', b.textContent === t); });
                renderSystemTab(tabContent, t);
            };
            tabs.appendChild(btn);
        })(tabNames[i]);
    }
    content.appendChild(tabs);
    content.appendChild(tabContent);
    renderSystemTab(tabContent, 'Status');
}

async function renderSystemTab(container, tab) {
    container.textContent = '';

    if (tab === 'Status') {
        var results = await Promise.all([api('/system/info'), api('/system/health-checks'), api('/system/disk-space')]);
        var info = results[0], health = results[1], disk = results[2];

        if (info) {
            var panel = el('div','panel');
            panel.appendChild(el('div','panel-header','System Information'));
            var body = el('div','panel-body');
            var rows = [
                ['Version', info.version], ['Application', info.app_name],
                ['Python', info.python_version], ['Platform', info.platform],
                ['Database', info.database], ['Database Path', info.database_path],
                ['Startup Directory', info.startup_dir], ['Media Root', info.media_root],
                ['Mode', info.mode], ['Host', info.host + ':' + info.port],
                ['Uptime Since', info.uptime_start ? new Date(info.uptime_start).toLocaleString() : 'Unknown'],
            ];
            for (var r = 0; r < rows.length; r++) {
                var row = el('div','table-row');
                row.style.display = 'flex';
                row.style.justifyContent = 'space-between';
                row.style.padding = '6px 0';
                row.style.borderBottom = '1px solid var(--border)';
                row.appendChild(el('span','text-dim', rows[r][0]));
                var val = el('span','');
                val.textContent = rows[r][1] || '';
                val.style.fontFamily = 'monospace';
                row.appendChild(val);
                body.appendChild(row);
            }
            panel.appendChild(body);
            container.appendChild(panel);
        }

        if (health && health.checks) {
            var hPanel = el('div','panel');
            hPanel.style.marginTop = '12px';
            hPanel.appendChild(el('div','panel-header','Health Checks'));
            var hBody = el('div','panel-body');
            for (var c = 0; c < health.checks.length; c++) {
                var check = health.checks[c];
                var hRow = el('div','table-row');
                hRow.style.display = 'flex';
                hRow.style.alignItems = 'center';
                hRow.style.gap = '8px';
                hRow.style.padding = '6px 0';
                var icon = check.type === 'ok' ? '\u2713' : check.type === 'warning' ? '\u26A0' : '\u2717';
                var color = check.type === 'ok' ? 'tag-green' : check.type === 'warning' ? 'tag-orange' : 'tag-red';
                hRow.appendChild(el('span','tag ' + color, icon));
                hRow.appendChild(el('span','',check.source));
                var msg = el('span','text-dim');
                msg.style.flex = '1';
                msg.style.textAlign = 'right';
                msg.textContent = check.message;
                hRow.appendChild(msg);
                hBody.appendChild(hRow);
            }
            hPanel.appendChild(hBody);
            container.appendChild(hPanel);
        }

        if (disk && disk.drives && disk.drives.length) {
            var dPanel = el('div','panel');
            dPanel.style.marginTop = '12px';
            dPanel.appendChild(el('div','panel-header','Disk Space'));
            var dBody = el('div','panel-body');
            for (var dd = 0; dd < disk.drives.length; dd++) {
                var d = disk.drives[dd];
                var dRow = el('div','');
                dRow.style.marginBottom = '12px';
                dRow.appendChild(el('div','', d.label + ' \u2014 ' + d.path));
                var barOuter = el('div','');
                barOuter.style.height = '20px';
                barOuter.style.background = 'var(--bg-secondary)';
                barOuter.style.borderRadius = '4px';
                barOuter.style.overflow = 'hidden';
                barOuter.style.margin = '4px 0';
                var barInner = el('div','');
                barInner.style.height = '100%';
                barInner.style.width = d.percent_used + '%';
                barInner.style.background = d.percent_used > 90 ? 'var(--red)' : d.percent_used > 75 ? 'var(--orange)' : 'var(--green)';
                barInner.style.borderRadius = '4px';
                barOuter.appendChild(barInner);
                dRow.appendChild(barOuter);
                dRow.appendChild(el('div','text-dim', fmtBytes(d.used) + ' / ' + fmtBytes(d.total) + ' (' + d.percent_used + '% used) \u2014 ' + fmtBytes(d.free) + ' free'));
                dBody.appendChild(dRow);
            }
            dPanel.appendChild(dBody);
            container.appendChild(dPanel);
        }

    } else if (tab === 'Tasks') {
        var data = await api('/system/tasks');
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Scheduled Tasks'));
        var body = el('div','panel-body');
        if (data && data.tasks) {
            for (var i = 0; i < data.tasks.length; i++) {
                (function(t) {
                    var row = el('div','table-row');
                    row.style.display = 'flex';
                    row.style.alignItems = 'center';
                    row.style.gap = '8px';
                    row.style.padding = '8px 0';
                    row.style.borderBottom = '1px solid var(--border)';
                    var info = el('div','');
                    info.style.flex = '1';
                    info.appendChild(el('div','',t.name));
                    var meta = el('div','text-dim');
                    meta.style.fontSize = '12px';
                    meta.textContent = t.description;
                    info.appendChild(meta);
                    row.appendChild(info);
                    row.appendChild(el('span','tag tag-cyan', t.interval_display));
                    row.appendChild(el('span','text-dim', 'Last: ' + (t.last_run === 'never' ? 'Never' : new Date(t.last_run).toLocaleTimeString())));
                    var runBtn = el('button','btn btn-sm','Run Now');
                    runBtn.onclick = async function() { await apiPost('/system/tasks/' + t.name + '/run', {}); toast(t.name + ' triggered'); };
                    row.appendChild(runBtn);
                    body.appendChild(row);
                })(data.tasks[i]);
            }
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Health') {
        var data = await api('/system/health-checks');
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Health Checks'));
        var body = el('div','panel-body');
        if (data && data.checks) {
            for (var i = 0; i < data.checks.length; i++) {
                var c = data.checks[i];
                var row = el('div','table-row');
                row.style.display = 'flex';
                row.style.alignItems = 'center';
                row.style.gap = '8px';
                row.style.padding = '8px 0';
                row.style.borderBottom = '1px solid var(--border)';
                var icon = c.type === 'ok' ? '\u2713' : c.type === 'warning' ? '\u26A0' : '\u2717';
                var color = c.type === 'ok' ? 'tag-green' : c.type === 'warning' ? 'tag-orange' : 'tag-red';
                row.appendChild(el('span','tag ' + color, icon + ' ' + c.source));
                var msg = el('span','');
                msg.style.flex = '1';
                msg.textContent = c.message;
                row.appendChild(msg);
                body.appendChild(row);
            }
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Events') {
        var curLevel = null;
        var filterBar = el('div','filter-bar');
        var levels = ['All','info','warn','error'];
        var eventList = el('div','panel');

        for (var i = 0; i < levels.length; i++) {
            (function(lv) {
                var b = el('button','btn btn-sm' + (lv === 'All' ? ' active' : ''), lv);
                b.onclick = async function() {
                    curLevel = lv === 'All' ? null : lv;
                    filterBar.querySelectorAll('button').forEach(function(x) { x.classList.remove('active'); });
                    b.classList.add('active');
                    await loadEvents();
                };
                filterBar.appendChild(b);
            })(levels[i]);
        }
        container.appendChild(filterBar);
        container.appendChild(eventList);

        async function loadEvents() {
            var url = '/events?page_size=100';
            if (curLevel) url += '&level=' + curLevel;
            var data = await api(url);
            eventList.textContent = '';
            eventList.appendChild(el('div','panel-header','Events (' + (data && data.total || 0) + ')'));
            var body = el('div','panel-body');
            if (!data || !data.events || !data.events.length) {
                body.appendChild(el('p','text-dim','No events recorded yet.'));
            } else {
                for (var i = 0; i < data.events.length; i++) {
                    var ev = data.events[i];
                    var row = el('div','table-row');
                    row.style.display = 'flex';
                    row.style.alignItems = 'center';
                    row.style.gap = '8px';
                    row.style.padding = '6px 0';
                    row.style.borderBottom = '1px solid var(--border)';
                    var lvColor = ev.level === 'error' ? 'tag-red' : ev.level === 'warn' ? 'tag-orange' : ev.level === 'debug' ? 'tag-cyan' : '';
                    row.appendChild(el('span','tag ' + lvColor, ev.level));
                    row.appendChild(el('span','tag', ev.category));
                    var msg = el('span','');
                    msg.style.flex = '1';
                    msg.textContent = ev.message;
                    row.appendChild(msg);
                    var time = el('span','text-dim');
                    time.style.fontSize = '12px';
                    time.textContent = ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '';
                    row.appendChild(time);
                    body.appendChild(row);
                }
            }
            eventList.appendChild(body);
            var clearBtn = el('button','btn btn-sm btn-danger','Clear Events');
            clearBtn.style.marginTop = '8px';
            clearBtn.onclick = async function() { await apiDelete('/events'); loadEvents(); };
            eventList.appendChild(clearBtn);
        }
        await loadEvents();

    } else if (tab === 'Logs') {
        var data = await api('/logs');
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Log Files'));
        var body = el('div','panel-body');
        if (!data || !data.files || !data.files.length) {
            body.appendChild(el('p','text-dim','No log files found. Logs are written to the logs/ directory.'));
        } else {
            for (var i = 0; i < data.files.length; i++) {
                (function(f) {
                    var row = el('div','table-row');
                    row.style.display = 'flex';
                    row.style.alignItems = 'center';
                    row.style.gap = '8px';
                    row.style.padding = '6px 0';
                    row.style.cursor = 'pointer';
                    row.style.borderBottom = '1px solid var(--border)';
                    row.appendChild(el('span','',f.name));
                    var spacer = el('span','');
                    spacer.style.flex = '1';
                    row.appendChild(spacer);
                    row.appendChild(el('span','text-dim',fmtBytes(f.size)));
                    row.onclick = async function() {
                        var logData = await api('/logs/' + f.name + '?lines=200');
                        if (logData && logData.lines) {
                            var viewer = el('div','panel log-viewer-container');
                            viewer.style.marginTop = '8px';
                            viewer.appendChild(el('div','panel-header',f.name + ' (last ' + logData.lines.length + ' lines)'));
                            var pre = el('pre','');
                            pre.style.maxHeight = '400px';
                            pre.style.overflow = 'auto';
                            pre.style.padding = '12px';
                            pre.style.fontSize = '12px';
                            pre.style.fontFamily = 'monospace';
                            pre.style.background = 'var(--bg-primary)';
                            pre.style.borderRadius = '4px';
                            pre.style.whiteSpace = 'pre-wrap';
                            pre.style.wordBreak = 'break-all';
                            pre.textContent = logData.lines.join('');
                            viewer.appendChild(pre);
                            var existing = container.querySelector('.log-viewer-container');
                            if (existing) existing.replaceWith(viewer);
                            else container.appendChild(viewer);
                        }
                    };
                    body.appendChild(row);
                })(data.files[i]);
            }
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Backups') {
        var data = await api('/system/backups');
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Database Backups'));
        var body = el('div','panel-body');
        var createBtn = el('button','btn btn-success','Create Backup Now');
        createBtn.onclick = async function() {
            var r = await apiPost('/system/backups', {});
            if (r) toast('Backup created: ' + r.filename);
            renderSystemTab(container, 'Backups');
        };
        body.appendChild(createBtn);
        if (data && data.length) {
            for (var i = 0; i < data.length; i++) {
                (function(b) {
                    var row = el('div','table-row');
                    row.style.display = 'flex';
                    row.style.alignItems = 'center';
                    row.style.gap = '8px';
                    row.style.padding = '8px 0';
                    row.style.borderBottom = '1px solid var(--border)';
                    row.appendChild(el('span','',b.filename));
                    var spacer = el('span','');
                    spacer.style.flex = '1';
                    row.appendChild(spacer);
                    row.appendChild(el('span','text-dim', fmtBytes(b.size)));
                    row.appendChild(el('span','tag', b.backup_type));
                    row.appendChild(el('span','text-dim', b.created_at ? new Date(b.created_at).toLocaleString() : ''));
                    var delBtn = el('button','btn btn-sm btn-danger','Delete');
                    delBtn.onclick = async function() { await apiDelete('/system/backups/' + b.id); renderSystemTab(container, 'Backups'); };
                    row.appendChild(delBtn);
                    body.appendChild(row);
                })(data[i]);
            }
        } else {
            body.appendChild(el('p','text-dim','No backups yet. Create one to protect your database.'));
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Tags') {
        var data = await api('/tags');
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Tags'));
        var body = el('div','panel-body');

        var addRow = el('div','');
        addRow.style.display = 'flex';
        addRow.style.gap = '8px';
        addRow.style.marginBottom = '12px';
        var nameIn = el('input','input');
        nameIn.placeholder = 'Tag name';
        var colorIn = el('input','');
        colorIn.type = 'color';
        colorIn.value = '#3b82f6';
        colorIn.style.width = '40px';
        colorIn.style.height = '36px';
        colorIn.style.border = 'none';
        colorIn.style.cursor = 'pointer';
        var addBtn = el('button','btn btn-success','Add Tag');
        addBtn.onclick = async function() {
            if (nameIn.value.trim()) {
                await apiPost('/tags', { name: nameIn.value.trim(), color: colorIn.value });
                renderSystemTab(container, 'Tags');
            }
        };
        addRow.appendChild(nameIn);
        addRow.appendChild(colorIn);
        addRow.appendChild(addBtn);
        body.appendChild(addRow);

        if (data && data.length) {
            for (var i = 0; i < data.length; i++) {
                (function(t) {
                    var row = el('div','table-row');
                    row.style.display = 'flex';
                    row.style.alignItems = 'center';
                    row.style.gap = '8px';
                    row.style.padding = '6px 0';
                    row.style.borderBottom = '1px solid var(--border)';
                    var dot = el('span','');
                    dot.style.width = '12px';
                    dot.style.height = '12px';
                    dot.style.borderRadius = '50%';
                    dot.style.background = t.color;
                    row.appendChild(dot);
                    row.appendChild(el('span','',t.name));
                    var spacer = el('span','');
                    spacer.style.flex = '1';
                    row.appendChild(spacer);
                    row.appendChild(el('span','text-dim', t.usage_count + ' uses'));
                    var delBtn = el('button','btn btn-sm btn-danger','Delete');
                    delBtn.onclick = async function() { await apiDelete('/tags/' + t.id); renderSystemTab(container, 'Tags'); };
                    row.appendChild(delBtn);
                    body.appendChild(row);
                })(data[i]);
            }
        } else {
            body.appendChild(el('p','text-dim','No tags created. Tags help organize media, indexers, and download clients.'));
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Custom Formats') {
        var data = await api('/custom-formats');
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Custom Formats'));
        var body = el('div','panel-body');
        var addBtn = el('button','btn btn-success','+ Add Custom Format');
        addBtn.onclick = function() { showCustomFormatEditor(container); };
        body.appendChild(addBtn);
        if (data && data.length) {
            for (var i = 0; i < data.length; i++) {
                (function(cf) {
                    var row = el('div','table-row');
                    row.style.display = 'flex';
                    row.style.alignItems = 'center';
                    row.style.gap = '8px';
                    row.style.padding = '8px 0';
                    row.style.borderBottom = '1px solid var(--border)';
                    row.appendChild(el('span','',cf.name));
                    var spacer = el('span','');
                    spacer.style.flex = '1';
                    row.appendChild(spacer);
                    row.appendChild(el('span','tag ' + (cf.score > 0 ? 'tag-green' : cf.score < 0 ? 'tag-red' : ''), 'Score: ' + cf.score));
                    row.appendChild(el('span','text-dim', (cf.specifications && cf.specifications.length || 0) + ' rules'));
                    var delBtn = el('button','btn btn-sm btn-danger','Delete');
                    delBtn.onclick = async function() { await apiDelete('/custom-formats/' + cf.id); renderSystemTab(container, 'Custom Formats'); };
                    row.appendChild(delBtn);
                    body.appendChild(row);
                })(data[i]);
            }
        } else {
            body.appendChild(el('p','text-dim','No custom formats. Create regex rules to score release names (e.g., prefer x265, block HDCAM).'));
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Import Lists') {
        var data = await api('/import-lists');
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Import Lists'));
        var body = el('div','panel-body');
        var addBtn = el('button','btn btn-success','+ Add Import List');
        addBtn.onclick = function() { showImportListEditor(container); };
        body.appendChild(addBtn);
        if (data && data.length) {
            for (var i = 0; i < data.length; i++) {
                (function(il) {
                    var row = el('div','table-row');
                    row.style.display = 'flex';
                    row.style.alignItems = 'center';
                    row.style.gap = '8px';
                    row.style.padding = '8px 0';
                    row.style.borderBottom = '1px solid var(--border)';
                    row.appendChild(el('span','',il.name));
                    var spacer = el('span','');
                    spacer.style.flex = '1';
                    row.appendChild(spacer);
                    row.appendChild(el('span','tag', il.list_type));
                    row.appendChild(el('span','tag ' + (il.enabled ? 'tag-green' : 'tag-red'), il.enabled ? 'Enabled' : 'Disabled'));
                    row.appendChild(el('span','text-dim', 'Last: ' + (il.last_sync || 'Never')));
                    var syncBtn = el('button','btn btn-sm','Sync Now');
                    syncBtn.onclick = async function() { var r = await apiPost('/import-lists/' + il.id + '/sync', {}); toast('Synced: ' + (r && r.synced || 0) + ' items'); };
                    row.appendChild(syncBtn);
                    var delBtn = el('button','btn btn-sm btn-danger','Delete');
                    delBtn.onclick = async function() { await apiDelete('/import-lists/' + il.id); renderSystemTab(container, 'Import Lists'); };
                    row.appendChild(delBtn);
                    body.appendChild(row);
                })(data[i]);
            }
        } else {
            body.appendChild(el('p','text-dim','No import lists configured. Import from TMDB Popular, TMDB Lists, or Trakt.'));
        }
        panel.appendChild(body);
        container.appendChild(panel);

    } else if (tab === 'Naming') {
        var data = await api('/naming');
        if (!data) return;
        var typeLabels = {movie:'Movies',tv:'TV Shows',music:'Music',book:'Books'};
        for (var i = 0; i < data.length; i++) {
            (function(cfg) {
                var panel = el('div','panel');
                panel.style.marginTop = '8px';
                var typeLabel = typeLabels[cfg.media_type] || cfg.media_type;
                panel.appendChild(el('div','panel-header', typeLabel + ' Naming'));
                var body = el('div','panel-body');
                var form = el('div','form-grid');

                // Rename files toggle
                form.appendChild(el('label','','Rename Files'));
                var renameCheck = el('input','');
                renameCheck.type = 'checkbox';
                renameCheck.checked = cfg.rename_files;
                form.appendChild(renameCheck);

                // Standard format
                form.appendChild(el('label','','Standard Format'));
                var stdIn = el('input','input');
                stdIn.value = cfg.standard_format;
                form.appendChild(stdIn);

                // Folder format
                form.appendChild(el('label','','Folder Format'));
                var folderIn = el('input','input');
                folderIn.value = cfg.folder_format;
                form.appendChild(folderIn);

                // Replace illegal
                form.appendChild(el('label','','Replace Illegal Characters'));
                var illegalCheck = el('input','');
                illegalCheck.type = 'checkbox';
                illegalCheck.checked = cfg.replace_illegal;
                form.appendChild(illegalCheck);

                // Colon replacement
                form.appendChild(el('label','','Colon Replacement'));
                var colonSelect = el('select','input');
                var colonOpts = [['dash','Replace with Dash'],['delete','Delete'],['space','Replace with Space']];
                for (var j = 0; j < colonOpts.length; j++) {
                    var opt = el('option','',colonOpts[j][1]);
                    opt.value = colonOpts[j][0];
                    if (cfg.colon_replacement === colonOpts[j][0]) opt.selected = true;
                    colonSelect.appendChild(opt);
                }
                form.appendChild(colonSelect);

                body.appendChild(form);
                var saveBtn = el('button','btn btn-success','Save');
                saveBtn.style.marginTop = '8px';
                saveBtn.onclick = async function() {
                    await apiPut('/naming', {
                        media_type: cfg.media_type,
                        rename_files: renameCheck.checked,
                        replace_illegal: illegalCheck.checked,
                        colon_replacement: colonSelect.value,
                        standard_format: stdIn.value,
                        folder_format: folderIn.value,
                    });
                    toast(typeLabel + ' naming saved');
                };
                body.appendChild(saveBtn);
                panel.appendChild(body);
                container.appendChild(panel);
            })(data[i]);
        }
    }
}

// Custom Format Editor modal
function showCustomFormatEditor(container) {
    var modal = el('div','modal-overlay');
    modal.onclick = function(e) { if (e.target === modal) modal.remove(); };
    var box = el('div','modal-box');
    box.style.maxWidth = '600px';
    box.appendChild(el('h3','','New Custom Format'));

    var form = el('div','form-grid');
    form.appendChild(el('label','','Name'));
    var cfName = el('input','input');
    cfName.placeholder = 'e.g., Prefer x265';
    form.appendChild(cfName);
    form.appendChild(el('label','','Score'));
    var cfScore = el('input','input');
    cfScore.type = 'number';
    cfScore.value = '0';
    cfScore.placeholder = 'Positive = prefer, Negative = avoid';
    form.appendChild(cfScore);
    box.appendChild(form);

    box.appendChild(el('h4','','Specifications (regex rules)'));
    var specList = el('div','');
    box.appendChild(specList);

    var addSpec = el('button','btn btn-sm','+ Add Rule');
    addSpec.onclick = function() {
        var specRow = el('div','');
        specRow.style.display = 'flex';
        specRow.style.gap = '4px';
        specRow.style.margin = '4px 0';
        specRow.style.alignItems = 'center';

        var fieldIn = el('input','input');
        fieldIn.placeholder = 'Field (release_title)';
        fieldIn.style.width = '120px';
        fieldIn.className = 'input spec-field';
        specRow.appendChild(fieldIn);

        var valIn = el('input','input');
        valIn.placeholder = 'Regex pattern';
        valIn.style.flex = '1';
        valIn.className = 'input spec-value';
        specRow.appendChild(valIn);

        var negLabel = el('label','','Negate');
        negLabel.style.fontSize = '12px';
        negLabel.style.whiteSpace = 'nowrap';
        var negCheck = el('input','');
        negCheck.type = 'checkbox';
        negCheck.className = 'spec-negate';
        negLabel.prepend(negCheck);
        specRow.appendChild(negLabel);

        var reqLabel = el('label','','Required');
        reqLabel.style.fontSize = '12px';
        reqLabel.style.whiteSpace = 'nowrap';
        var reqCheck = el('input','');
        reqCheck.type = 'checkbox';
        reqCheck.checked = true;
        reqCheck.className = 'spec-required';
        reqLabel.prepend(reqCheck);
        specRow.appendChild(reqLabel);

        var rmBtn = el('button','btn btn-sm btn-danger','X');
        rmBtn.onclick = function() { specRow.remove(); };
        specRow.appendChild(rmBtn);

        specList.appendChild(specRow);
    };
    box.appendChild(addSpec);

    var saveBtn = el('button','btn btn-success','Save');
    saveBtn.style.marginTop = '12px';
    saveBtn.onclick = async function() {
        var specs = [];
        var rows = specList.querySelectorAll('div');
        for (var i = 0; i < rows.length; i++) {
            var field = rows[i].querySelector('.spec-field');
            var value = rows[i].querySelector('.spec-value');
            if (field && value && field.value && value.value) {
                specs.push({
                    field: field.value, value: value.value, regex: true,
                    negate: rows[i].querySelector('.spec-negate') ? rows[i].querySelector('.spec-negate').checked : false,
                    required: rows[i].querySelector('.spec-required') ? rows[i].querySelector('.spec-required').checked : false,
                });
            }
        }
        await apiPost('/custom-formats', {
            name: cfName.value,
            score: parseInt(cfScore.value) || 0,
            specifications: specs,
        });
        modal.remove();
        renderSystemTab(container, 'Custom Formats');
    };
    box.appendChild(saveBtn);
    modal.appendChild(box);
    document.body.appendChild(modal);
}

// Import List Editor modal
function showImportListEditor(container) {
    var modal = el('div','modal-overlay');
    modal.onclick = function(e) { if (e.target === modal) modal.remove(); };
    var box = el('div','modal-box');
    box.appendChild(el('h3','','Add Import List'));

    var form = el('div','form-grid');
    form.appendChild(el('label','','Name'));
    var ilName = el('input','input');
    ilName.placeholder = 'e.g., TMDB Popular Movies';
    form.appendChild(ilName);

    form.appendChild(el('label','','Type'));
    var ilType = el('select','input');
    var types = [['tmdb_popular','TMDB Popular'],['tmdb_upcoming','TMDB Upcoming'],['tmdb_trending','TMDB Trending'],['tmdb_list','TMDB List (by ID)'],['trakt_watchlist','Trakt Watchlist'],['imdb_watchlist','IMDB Watchlist']];
    for (var i = 0; i < types.length; i++) {
        var opt = el('option','',types[i][1]);
        opt.value = types[i][0];
        ilType.appendChild(opt);
    }
    form.appendChild(ilType);

    form.appendChild(el('label','','Media Type'));
    var ilMedia = el('select','input');
    var mediaOpts = [['movie','Movie'],['tv','TV']];
    for (var i = 0; i < mediaOpts.length; i++) {
        var opt = el('option','',mediaOpts[i][1]);
        opt.value = mediaOpts[i][0];
        ilMedia.appendChild(opt);
    }
    form.appendChild(ilMedia);

    form.appendChild(el('label','','Sync Interval (min)'));
    var ilInterval = el('input','input');
    ilInterval.type = 'number';
    ilInterval.value = '360';
    form.appendChild(ilInterval);

    form.appendChild(el('label','','Search on Add'));
    var ilSearch = el('input','');
    ilSearch.type = 'checkbox';
    ilSearch.checked = true;
    form.appendChild(ilSearch);

    box.appendChild(form);
    var saveBtn = el('button','btn btn-success','Save');
    saveBtn.style.marginTop = '8px';
    saveBtn.onclick = async function() {
        await apiPost('/import-lists', {
            name: ilName.value,
            list_type: ilType.value,
            media_type: ilMedia.value,
            sync_interval: parseInt(ilInterval.value) || 360,
            search_on_add: ilSearch.checked,
        });
        modal.remove();
        renderSystemTab(container, 'Import Lists');
    };
    box.appendChild(saveBtn);
    modal.appendChild(box);
    document.body.appendChild(modal);
}

// ── Connect — notifications + custom scripts ─────────────
async function renderConnect() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Connect'));
    content.appendChild(el('p','page-subtitle','Notifications, media servers, and custom scripts triggered on events'));

    var data = await api('/connect');
    var panel = el('div','panel');
    var head = el('div','panel-header');
    head.appendChild(el('span','','Connections'));
    var addBtn = el('button','btn btn-sm btn-success','+ Add Connection');
    head.appendChild(addBtn);
    panel.appendChild(head);
    var body = el('div','panel-body');

    if (data && data.length) {
        for (var i = 0; i < data.length; i++) {
            (function(c) {
                var row = el('div','table-row');
                row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border)';
                row.appendChild(el('span','tag ' + (c.enabled ? 'tag-green' : 'tag-red'), c.enabled ? 'ON' : 'OFF'));
                row.appendChild(el('span','tag tag-cyan', c.client_type));
                var info = el('span','',c.name); info.style.flex = '1'; row.appendChild(info);
                var events = [];
                if (c.on_grab) events.push('Grab');
                if (c.on_download) events.push('Download');
                if (c.on_upgrade) events.push('Upgrade');
                if (c.on_rename) events.push('Rename');
                if (c.on_delete) events.push('Delete');
                if (c.on_health) events.push('Health');
                row.appendChild(el('span','text-dim', events.join(', ') || 'No events'));
                var testBtn = el('button','btn btn-sm','Test');
                testBtn.onclick = async function() {
                    var r = await apiPost('/connect/' + c.id + '/test', {});
                    toast(r && r.success ? 'Test passed' : 'Test failed');
                };
                row.appendChild(testBtn);
                var delBtn = el('button','btn btn-sm btn-danger','Remove');
                delBtn.onclick = async function() { await apiDelete('/connect/' + c.id); renderConnect(); };
                row.appendChild(delBtn);
                body.appendChild(row);
            })(data[i]);
        }
    } else {
        body.appendChild(el('p','text-dim','No connections configured. Add Discord, webhooks, Plex, custom scripts, etc.'));
    }
    panel.appendChild(body);
    content.appendChild(panel);

    // Available types
    var types = [
        ['discord','Discord','Webhook notifications to Discord'],
        ['telegram','Telegram','Bot notifications to Telegram'],
        ['slack','Slack','Webhook to Slack'],
        ['webhook','Webhook','Generic HTTP webhook (POST JSON)'],
        ['email','Email','Email via SMTP'],
        ['custom_script','Custom Script','Run a script on events'],
        ['plex','Plex','Notify Plex to scan'],
        ['emby','Emby','Notify Emby to scan'],
        ['jellyfin','Jellyfin','Notify Jellyfin to scan'],
        ['kodi','Kodi','Notify Kodi to update'],
    ];

    addBtn.onclick = function() {
        var modal = el('div','modal-overlay');
        modal.onclick = function(e) { if (e.target === modal) modal.remove(); };
        var box = el('div','modal-box');
        box.appendChild(el('h3','','Add Connection'));
        var form = el('div','form-grid');
        form.appendChild(el('label','','Name'));
        var nameIn = el('input','input'); nameIn.placeholder = 'e.g., Discord Notifications'; form.appendChild(nameIn);
        form.appendChild(el('label','','Type'));
        var typeSelect = el('select','input');
        for (var j = 0; j < types.length; j++) { var opt = el('option','',types[j][1]); opt.value = types[j][0]; typeSelect.appendChild(opt); }
        form.appendChild(typeSelect);
        form.appendChild(el('label','','URL / Webhook / Path'));
        var urlIn = el('input','input'); urlIn.placeholder = 'https://discord.com/api/webhooks/...'; form.appendChild(urlIn);
        form.appendChild(el('label','','Events'));
        var evDiv = el('div',''); evDiv.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px';
        var eventNames = ['on_grab','on_download','on_upgrade','on_rename','on_delete','on_health'];
        var eventChecks = {};
        for (var j = 0; j < eventNames.length; j++) {
            var lbl = el('label','',eventNames[j].replace('on_',''));
            lbl.style.cssText = 'font-size:12px;display:flex;align-items:center;gap:4px';
            var cb = el('input',''); cb.type = 'checkbox';
            if (eventNames[j] === 'on_download') cb.checked = true;
            eventChecks[eventNames[j]] = cb;
            lbl.prepend(cb);
            evDiv.appendChild(lbl);
        }
        form.appendChild(evDiv);
        box.appendChild(form);
        var saveBtn2 = el('button','btn btn-success','Save');
        saveBtn2.style.marginTop = '8px';
        saveBtn2.onclick = async function() {
            var payload = { name: nameIn.value, client_type: typeSelect.value,
                config: {url: urlIn.value, webhook_url: urlIn.value, path: urlIn.value} };
            for (var k in eventChecks) payload[k] = eventChecks[k].checked;
            await apiPost('/connect', payload);
            modal.remove(); renderConnect();
        };
        box.appendChild(saveBtn2);
        modal.appendChild(box);
        document.body.appendChild(modal);
    };
}

// ── Music ────────────────────────────────────────────────
// ── Music / Books / Comics — use shared renderMediaTab ──
async function renderMusic() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Music'));
    content.appendChild(el('p','page-subtitle','Music library \u2014 replaces Lidarr'));
    var tabs = el('div','settings-tabs');
    var tabContent = el('div','');
    ['On Disk','Library','Upcoming','Popular','Search'].forEach(function(t,i) {
        var btn = el('button','settings-tab'+(i===0?' active':''),t);
        btn.onclick = function() {
            tabs.querySelectorAll('.settings-tab').forEach(function(b){b.classList.remove('active');});
            btn.classList.add('active');
            renderMediaTab(tabContent,'music',t);
        };
        tabs.appendChild(btn);
    });
    content.appendChild(tabs);
    content.appendChild(tabContent);
    renderMediaTab(tabContent,'music','On Disk');
}

async function renderBooks() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Books & Audiobooks'));
    content.appendChild(el('p','page-subtitle','Ebooks & audiobooks \u2014 replaces Readarr'));
    var tabs = el('div','settings-tabs');
    var tabContent = el('div','');
    ['On Disk','Library','Upcoming','Popular','Search'].forEach(function(t,i) {
        var btn = el('button','settings-tab'+(i===0?' active':''),t);
        btn.onclick = function() {
            tabs.querySelectorAll('.settings-tab').forEach(function(b){b.classList.remove('active');});
            btn.classList.add('active');
            renderMediaTab(tabContent,'books',t);
        };
        tabs.appendChild(btn);
    });
    content.appendChild(tabs);
    content.appendChild(tabContent);
    renderMediaTab(tabContent,'books','On Disk');
}

async function renderComics() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Comics'));
    content.appendChild(el('p','page-subtitle','Comic management \u2014 replaces Mylar3'));
    var tabs = el('div','settings-tabs');
    var tabContent = el('div','');
    ['On Disk','Library','Upcoming','Popular','Search'].forEach(function(t,i) {
        var btn = el('button','settings-tab'+(i===0?' active':''),t);
        btn.onclick = function() {
            tabs.querySelectorAll('.settings-tab').forEach(function(b){b.classList.remove('active');});
            btn.classList.add('active');
            renderMediaTab(tabContent,'comics',t);
        };
        tabs.appendChild(btn);
    });
    content.appendChild(tabs);
    content.appendChild(tabContent);
    renderMediaTab(tabContent,'comics','On Disk');
}
