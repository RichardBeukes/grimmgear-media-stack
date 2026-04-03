// GrimmGear Mediarr — Calendar, Blocklist, System, Music, Books, Comics Pages
// Loaded after app.js

// ── Calendar ─────────────────────────────────────────────
async function renderCalendar() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Calendar'));
    content.appendChild(el('p','page-subtitle','Upcoming episodes, movie releases, and monitored items'));

    const now = new Date();
    const start = new Date(now); start.setDate(start.getDate() - 7);
    const end = new Date(now); end.setDate(end.getDate() + 30);
    const startStr = start.toISOString().split('T')[0];
    const endStr = end.toISOString().split('T')[0];

    const data = await api('/calendar?start=' + startStr + '&end=' + endStr);
    if (!data || !data.events || data.events.length === 0) {
        const empty = el('div','panel');
        const emptyBody = el('div','panel-body');
        emptyBody.appendChild(el('p','','No calendar events. Add movies or TV series to see upcoming releases.'));
        empty.appendChild(emptyBody);
        content.appendChild(empty);
        return;
    }

    // Group events by date
    const grouped = {};
    for (const ev of data.events) {
        const d = ev.date || 'Unknown';
        if (!grouped[d]) grouped[d] = [];
        grouped[d].push(ev);
    }

    // View toggle buttons
    const nav = el('div','filter-bar');
    const viewMonth = el('button','btn btn-sm btn-ghost','Month View');
    const viewList = el('button','btn btn-sm active','List View');
    nav.appendChild(viewMonth);
    nav.appendChild(viewList);
    content.appendChild(nav);

    // Month grid
    const calGrid = el('div','calendar-grid');
    calGrid.style.display = 'none';
    calGrid.style.gridTemplateColumns = 'repeat(7,1fr)';
    calGrid.style.gap = '2px';
    calGrid.style.marginTop = '12px';

    const dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    for (const dn of dayNames) {
        const hdr = el('div','','');
        hdr.textContent = dn;
        hdr.style.textAlign = 'center';
        hdr.style.padding = '4px';
        hdr.style.fontWeight = '600';
        hdr.style.color = 'var(--text-dim)';
        hdr.style.fontSize = '12px';
        calGrid.appendChild(hdr);
    }

    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const firstDay = monthStart.getDay();
    for (let i = 0; i < firstDay; i++) calGrid.appendChild(el('div',''));

    const todayStr = now.toISOString().split('T')[0];
    for (let d = 1; d <= monthEnd.getDate(); d++) {
        const dateStr = now.getFullYear() + '-' + String(now.getMonth()+1).padStart(2,'0') + '-' + String(d).padStart(2,'0');
        const cell = el('div','');
        cell.style.minHeight = '60px';
        cell.style.padding = '4px';
        cell.style.background = 'var(--card-bg)';
        cell.style.borderRadius = '4px';
        cell.style.fontSize = '12px';
        const dayNum = el('div','',String(d));
        dayNum.style.fontWeight = '600';
        if (dateStr === todayStr) dayNum.style.color = 'var(--accent)';
        cell.appendChild(dayNum);
        const dayEvents = grouped[dateStr] || [];
        for (const ev of dayEvents.slice(0, 3)) {
            const dot = el('div','',ev.title.substring(0, 20));
            dot.style.fontSize = '10px';
            dot.style.padding = '1px 3px';
            dot.style.marginTop = '1px';
            dot.style.borderRadius = '2px';
            dot.style.overflow = 'hidden';
            dot.style.whiteSpace = 'nowrap';
            dot.style.textOverflow = 'ellipsis';
            dot.style.background = ev.type === 'movie' ? 'var(--yellow)' : 'var(--cyan)';
            dot.style.color = '#000';
            cell.appendChild(dot);
        }
        calGrid.appendChild(cell);
    }
    content.appendChild(calGrid);

    // List view
    const listDiv = el('div','');
    const sortedDates = Object.keys(grouped).sort();
    for (const date of sortedDates) {
        const section = el('div','panel');
        section.style.marginTop = '8px';
        const isToday = date === todayStr;
        const isPast = date < todayStr;
        const headerText = date + (isToday ? '  (Today)' : isPast ? '  (Past)' : '');
        const header = el('div','panel-header', headerText);
        if (isToday) header.style.color = 'var(--accent)';
        if (isPast) header.style.opacity = '0.6';
        section.appendChild(header);
        const body = el('div','panel-body');
        for (const ev of grouped[date]) {
            const row = el('div','table-row');
            row.style.display = 'flex';
            row.style.alignItems = 'center';
            row.style.gap = '8px';
            row.style.padding = '6px 0';
            const typeTag = el('span','tag ' + (ev.type === 'movie' ? 'tag-yellow' : 'tag-cyan'), ev.type);
            row.appendChild(typeTag);
            const title = el('span','',ev.title);
            title.style.flex = '1';
            row.appendChild(title);
            row.appendChild(el('span','tag ' + (ev.has_file ? 'tag-green' : 'tag-orange'), ev.has_file ? 'On Disk' : 'Missing'));
            body.appendChild(row);
        }
        section.appendChild(body);
        listDiv.appendChild(section);
    }
    content.appendChild(listDiv);

    viewMonth.onclick = function() {
        calGrid.style.display = 'grid';
        listDiv.style.display = 'none';
        viewMonth.classList.add('active');
        viewList.classList.remove('active');
    };
    viewList.onclick = function() {
        calGrid.style.display = 'none';
        listDiv.style.display = '';
        viewList.classList.add('active');
        viewMonth.classList.remove('active');
    };
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

// ── Music ────────────────────────────────────────────────
async function renderMusic() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Music'));
    content.appendChild(el('p','page-subtitle','Music library management \u2014 replaces Lidarr'));

    var results = await Promise.all([api('/music/library'), api('/quality-profiles/by-type/music'), api('/quality-definitions')]);
    var library = results[0], profiles = results[1], qualDefs = results[2];

    var statsDiv = el('div','stat-row');
    var trackCount = library && library.items ? library.items.length : 0;
    var totalSize = 0;
    if (library && library.items) library.items.forEach(function(i) { totalSize += i.size || 0; });
    function mkStat(label, value, sub, color) {
        var c = el('div','stat-card');
        var bar = el('div','accent-bar'); bar.style.background = color; c.appendChild(bar);
        c.appendChild(el('div','stat-label',label));
        c.appendChild(el('div','stat-value',String(value)));
        c.appendChild(el('div','stat-sub',sub));
        return c;
    }
    statsDiv.appendChild(mkStat('Tracks', trackCount, fmtBytes(totalSize), 'var(--green)'));
    statsDiv.appendChild(mkStat('Profiles', profiles ? profiles.length : 0, 'music quality', 'var(--cyan)'));
    content.appendChild(statsDiv);

    // Search
    var searchBar = el('div',''); searchBar.style.cssText = 'display:flex;gap:8px;margin:12px 0';
    var searchIn = el('input','input'); searchIn.placeholder = 'Search artists on MusicBrainz...'; searchIn.style.flex = '1';
    var searchBtn = el('button','btn','Search');
    searchBar.appendChild(searchIn); searchBar.appendChild(searchBtn);
    content.appendChild(searchBar);
    var searchResults = el('div','');
    content.appendChild(searchResults);
    searchBtn.onclick = async function() {
        if (!searchIn.value.trim()) return;
        searchResults.textContent = '';
        var data = await api('/music/search/artists?q=' + encodeURIComponent(searchIn.value));
        if (!data || !data.length) { searchResults.appendChild(el('p','text-dim','No results')); return; }
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Results (' + data.length + ')'));
        var body = el('div','panel-body');
        for (var i = 0; i < data.length; i++) {
            var a = data[i];
            var row = el('div','table-row'); row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)';
            row.appendChild(el('span','',a.name || a.title || ''));
            var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
            if (a.type) row.appendChild(el('span','tag',a.type));
            if (a.country) row.appendChild(el('span','text-dim',a.country));
            body.appendChild(row);
        }
        panel.appendChild(body); searchResults.appendChild(panel);
    };
    searchIn.onkeydown = function(e) { if (e.key === 'Enter') searchBtn.click(); };

    // Quality profiles
    if (profiles && profiles.length) {
        var qPanel = el('div','panel'); qPanel.style.marginTop = '12px';
        qPanel.appendChild(el('div','panel-header','Music Quality Profiles'));
        var qBody = el('div','panel-body');
        for (var i = 0; i < profiles.length; i++) {
            var row = el('div','table-row'); row.style.cssText = 'display:flex;padding:6px 0;gap:8px';
            row.appendChild(el('span','',profiles[i].name));
            var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
            row.appendChild(el('span','tag tag-cyan', profiles[i].cutoff));
            row.appendChild(el('span','text-dim', 'Min: ' + profiles[i].min_quality));
            qBody.appendChild(row);
        }
        qPanel.appendChild(qBody); content.appendChild(qPanel);
    }

    // Quality definitions
    if (qualDefs && qualDefs.music) {
        var dPanel = el('div','panel'); dPanel.style.marginTop = '12px';
        dPanel.appendChild(el('div','panel-header','Music Quality Definitions'));
        var dBody = el('div','panel-body');
        for (var i = 0; i < qualDefs.music.length; i++) {
            var q = qualDefs.music[i];
            var row = el('div','table-row'); row.style.cssText = 'display:flex;padding:4px 0;gap:8px';
            row.appendChild(el('span','',q.title));
            var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
            row.appendChild(el('span','text-dim', q.min_size + '-' + q.max_size + ' MB/track'));
            dBody.appendChild(row);
        }
        dPanel.appendChild(dBody); content.appendChild(dPanel);
    }

    // Library
    if (library && library.items && library.items.length) {
        var lPanel = el('div','panel'); lPanel.style.marginTop = '12px';
        lPanel.appendChild(el('div','panel-header','Library (' + library.items.length + ' items)'));
        var lBody = el('div','panel-body'); lBody.style.cssText = 'max-height:400px;overflow:auto';
        for (var i = 0; i < Math.min(library.items.length, 100); i++) {
            var item = library.items[i];
            var row = el('div','table-row'); row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px';
            row.appendChild(el('span','',item.name));
            var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
            row.appendChild(el('span','text-dim',fmtBytes(item.size)));
            lBody.appendChild(row);
        }
        if (library.items.length > 100) lBody.appendChild(el('p','text-dim','... and ' + (library.items.length - 100) + ' more'));
        lPanel.appendChild(lBody); content.appendChild(lPanel);
    }
}

// ── Books ────────────────────────────────────────────────
async function renderBooks() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Books & Audiobooks'));
    content.appendChild(el('p','page-subtitle','Ebooks, audiobooks \u2014 replaces Readarr'));

    var tabs = el('div','settings-tabs');
    var tabNames = ['Ebooks','Audiobooks','Search','Quality'];
    var tabContent = el('div','');
    for (var i = 0; i < tabNames.length; i++) {
        (function(t, idx) {
            var btn = el('button','settings-tab' + (idx === 0 ? ' active' : ''), t);
            btn.onclick = function() {
                tabs.querySelectorAll('.settings-tab').forEach(function(b) { b.classList.toggle('active', b.textContent === t); });
                renderBookTab(tabContent, t);
            };
            tabs.appendChild(btn);
        })(tabNames[i], i);
    }
    content.appendChild(tabs);
    content.appendChild(tabContent);
    renderBookTab(tabContent, 'Ebooks');
}

async function renderBookTab(container, tab) {
    container.textContent = '';
    if (tab === 'Ebooks') {
        var results = await Promise.all([api('/books/library'), api('/quality-profiles/by-type/book')]);
        var library = results[0], profiles = results[1];
        if (profiles && profiles.length) {
            var pPanel = el('div','panel');
            pPanel.appendChild(el('div','panel-header','Ebook Quality Profiles'));
            var pBody = el('div','panel-body');
            for (var i = 0; i < profiles.length; i++) {
                var row = el('div','table-row'); row.style.cssText = 'display:flex;padding:6px 0;gap:8px';
                row.appendChild(el('span','',profiles[i].name));
                var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
                row.appendChild(el('span','tag tag-cyan',profiles[i].cutoff));
                pBody.appendChild(row);
            }
            pPanel.appendChild(pBody); container.appendChild(pPanel);
        }
        if (library && library.books && library.books.length) {
            var lPanel = el('div','panel'); lPanel.style.marginTop = '12px';
            lPanel.appendChild(el('div','panel-header','Library (' + library.books.length + ')'));
            var lBody = el('div','panel-body'); lBody.style.cssText = 'max-height:400px;overflow:auto';
            for (var i = 0; i < Math.min(library.books.length, 100); i++) {
                var b = library.books[i];
                var row = el('div','table-row'); row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 0';
                row.appendChild(el('span','',b.name));
                var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
                row.appendChild(el('span','tag',b.format.toUpperCase()));
                row.appendChild(el('span','text-dim',fmtBytes(b.size)));
                lBody.appendChild(row);
            }
            lPanel.appendChild(lBody); container.appendChild(lPanel);
        } else {
            container.appendChild(el('p','text-dim','No ebooks found. Add books to D:\\Media\\Books.'));
        }
    } else if (tab === 'Audiobooks') {
        var profiles = await api('/quality-profiles/by-type/audiobook');
        if (profiles && profiles.length) {
            var pPanel = el('div','panel');
            pPanel.appendChild(el('div','panel-header','Audiobook Quality Profiles'));
            var pBody = el('div','panel-body');
            for (var i = 0; i < profiles.length; i++) {
                var row = el('div','table-row'); row.style.cssText = 'display:flex;padding:6px 0;gap:8px';
                row.appendChild(el('span','',profiles[i].name));
                var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
                row.appendChild(el('span','tag tag-green',profiles[i].cutoff));
                pBody.appendChild(row);
            }
            pPanel.appendChild(pBody); container.appendChild(pPanel);
        }
        var qualDefs = await api('/quality-definitions');
        if (qualDefs && qualDefs.audiobook) {
            var dPanel = el('div','panel'); dPanel.style.marginTop = '12px';
            dPanel.appendChild(el('div','panel-header','Audiobook Quality Definitions'));
            var dBody = el('div','panel-body');
            for (var i = 0; i < qualDefs.audiobook.length; i++) {
                var q = qualDefs.audiobook[i];
                var row = el('div','table-row'); row.style.cssText = 'display:flex;padding:4px 0;gap:8px';
                row.appendChild(el('span','',q.title));
                var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
                row.appendChild(el('span','text-dim',q.min_size + '-' + q.max_size + ' MB'));
                dBody.appendChild(row);
            }
            dPanel.appendChild(dBody); container.appendChild(dPanel);
        }
        container.appendChild(el('p','text-dim','Add audiobooks to D:\\Media\\Audiobooks.'));
    } else if (tab === 'Search') {
        var searchBar = el('div',''); searchBar.style.cssText = 'display:flex;gap:8px;margin:12px 0';
        var searchIn = el('input','input'); searchIn.placeholder = 'Search books on OpenLibrary...'; searchIn.style.flex = '1';
        var searchBtn = el('button','btn','Search');
        searchBar.appendChild(searchIn); searchBar.appendChild(searchBtn);
        container.appendChild(searchBar);
        var resultsDiv = el('div',''); container.appendChild(resultsDiv);
        searchBtn.onclick = async function() {
            if (!searchIn.value.trim()) return;
            resultsDiv.textContent = '';
            var data = await api('/books/search?q=' + encodeURIComponent(searchIn.value));
            if (!data || !data.length) { resultsDiv.appendChild(el('p','text-dim','No results')); return; }
            var panel = el('div','panel');
            panel.appendChild(el('div','panel-header','Results (' + data.length + ')'));
            var body = el('div','panel-body');
            for (var i = 0; i < data.length; i++) {
                var b = data[i];
                var row = el('div','table-row'); row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border)';
                if (b.cover_url) { var img = el('img',''); img.src = b.cover_url; img.style.cssText = 'width:40px;height:60px;object-fit:cover;border-radius:4px'; row.appendChild(img); }
                var info = el('div',''); info.style.flex = '1';
                info.appendChild(el('div','',b.title));
                info.appendChild(el('div','text-dim',b.author + (b.year ? ' (' + b.year + ')' : '')));
                row.appendChild(info);
                if (b.isbn) row.appendChild(el('span','tag','ISBN: ' + b.isbn));
                body.appendChild(row);
            }
            panel.appendChild(body); resultsDiv.appendChild(panel);
        };
        searchIn.onkeydown = function(e) { if (e.key === 'Enter') searchBtn.click(); };
    } else if (tab === 'Quality') {
        var qualDefs = await api('/quality-definitions');
        if (qualDefs && qualDefs.book) {
            var panel = el('div','panel');
            panel.appendChild(el('div','panel-header','Ebook Quality Definitions'));
            var body = el('div','panel-body');
            for (var i = 0; i < qualDefs.book.length; i++) {
                var q = qualDefs.book[i];
                var row = el('div','table-row'); row.style.cssText = 'display:flex;padding:4px 0;gap:8px';
                row.appendChild(el('span','',q.title));
                var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
                row.appendChild(el('span','text-dim',q.min_size + '-' + q.max_size + ' MB'));
                body.appendChild(row);
            }
            panel.appendChild(body); container.appendChild(panel);
        }
    }
}

// ── Comics ───────────────────────────────────────────────
async function renderComics() {
    content.textContent = '';
    content.appendChild(el('h1','page-title','Comics'));
    content.appendChild(el('p','page-subtitle','Comic management \u2014 replaces Mylar3'));

    var results = await Promise.all([api('/comics/library'), api('/quality-profiles/by-type/comic'), api('/quality-definitions')]);
    var library = results[0], profiles = results[1], qualDefs = results[2];

    var statsDiv = el('div','stat-row');
    var comicCount = library && library.comics ? library.comics.length : 0;
    function mkStat(label, value, sub, color) {
        var c = el('div','stat-card');
        var bar = el('div','accent-bar'); bar.style.background = color; c.appendChild(bar);
        c.appendChild(el('div','stat-label',label));
        c.appendChild(el('div','stat-value',String(value)));
        c.appendChild(el('div','stat-sub',sub));
        return c;
    }
    statsDiv.appendChild(mkStat('Comics', comicCount, 'on disk', 'var(--orange)'));
    statsDiv.appendChild(mkStat('Profiles', profiles ? profiles.length : 0, 'quality', 'var(--cyan)'));
    content.appendChild(statsDiv);

    // Search
    var searchBar = el('div',''); searchBar.style.cssText = 'display:flex;gap:8px;margin:12px 0';
    var searchIn = el('input','input'); searchIn.placeholder = 'Search comics on Comic Vine...'; searchIn.style.flex = '1';
    var searchBtn = el('button','btn','Search');
    searchBar.appendChild(searchIn); searchBar.appendChild(searchBtn);
    content.appendChild(searchBar);
    var searchResults = el('div',''); content.appendChild(searchResults);
    searchBtn.onclick = async function() {
        if (!searchIn.value.trim()) return;
        searchResults.textContent = '';
        var data = await api('/comics/search?q=' + encodeURIComponent(searchIn.value));
        if (!data || !data.length) { searchResults.appendChild(el('p','text-dim','No results')); return; }
        var panel = el('div','panel');
        panel.appendChild(el('div','panel-header','Results (' + data.length + ')'));
        var body = el('div','panel-body');
        for (var i = 0; i < data.length; i++) {
            var c = data[i];
            var row = el('div','table-row'); row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border)';
            if (c.cover_url) { var img = el('img',''); img.src = c.cover_url; img.style.cssText = 'width:50px;height:75px;object-fit:cover;border-radius:4px'; row.appendChild(img); }
            var info = el('div',''); info.style.flex = '1';
            info.appendChild(el('div','',c.title));
            info.appendChild(el('div','text-dim',(c.publisher || '') + (c.year ? ' (' + c.year + ')' : '') + ' \u2014 ' + c.issues + ' issues'));
            row.appendChild(info);
            body.appendChild(row);
        }
        panel.appendChild(body); searchResults.appendChild(panel);
    };
    searchIn.onkeydown = function(e) { if (e.key === 'Enter') searchBtn.click(); };

    // Quality profiles
    if (profiles && profiles.length) {
        var qPanel = el('div','panel'); qPanel.style.marginTop = '12px';
        qPanel.appendChild(el('div','panel-header','Comic Quality Profiles'));
        var qBody = el('div','panel-body');
        for (var i = 0; i < profiles.length; i++) {
            var row = el('div','table-row'); row.style.cssText = 'display:flex;padding:6px 0;gap:8px';
            row.appendChild(el('span','',profiles[i].name));
            var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
            row.appendChild(el('span','tag tag-orange',profiles[i].cutoff));
            qBody.appendChild(row);
        }
        qPanel.appendChild(qBody); content.appendChild(qPanel);
    }

    // Quality definitions
    if (qualDefs && qualDefs.comic) {
        var dPanel = el('div','panel'); dPanel.style.marginTop = '12px';
        dPanel.appendChild(el('div','panel-header','Comic Quality Definitions'));
        var dBody = el('div','panel-body');
        for (var i = 0; i < qualDefs.comic.length; i++) {
            var q = qualDefs.comic[i];
            var row = el('div','table-row'); row.style.cssText = 'display:flex;padding:4px 0;gap:8px';
            row.appendChild(el('span','',q.title));
            var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
            row.appendChild(el('span','text-dim',q.min_size + '-' + q.max_size + ' MB'));
            dBody.appendChild(row);
        }
        dPanel.appendChild(dBody); content.appendChild(dPanel);
    }

    // Library
    if (library && library.comics && library.comics.length) {
        var lPanel = el('div','panel'); lPanel.style.marginTop = '12px';
        lPanel.appendChild(el('div','panel-header','Comic Library (' + library.comics.length + ')'));
        var lBody = el('div','panel-body'); lBody.style.cssText = 'max-height:400px;overflow:auto';
        for (var i = 0; i < Math.min(library.comics.length, 100); i++) {
            var c = library.comics[i];
            var row = el('div','table-row'); row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 0';
            row.appendChild(el('span','',c.name));
            var sp = el('span',''); sp.style.flex = '1'; row.appendChild(sp);
            row.appendChild(el('span','tag',c.format.toUpperCase()));
            row.appendChild(el('span','text-dim',c.series));
            row.appendChild(el('span','text-dim',fmtBytes(c.size)));
            lBody.appendChild(row);
        }
        lPanel.appendChild(lBody); content.appendChild(lPanel);
    } else {
        content.appendChild(el('p','text-dim','No comics found. Add comics to D:\\Media\\Comics.'));
    }
}
