"use strict";

var tg = window.Telegram && window.Telegram.WebApp;
var COUNTRIES = [
  { code: "RU", title: "Россия", cities: ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань"] },
  { code: "UA", title: "Украина", cities: ["Киев", "Харьков", "Одесса"] },
  { code: "BY", title: "Беларусь", cities: ["Минск", "Гомель"] },
  { code: "KZ", title: "Казахстан", cities: ["Алматы", "Астана"] },
  { code: "UZ", title: "Узбекистан", cities: ["Ташкент", "Самарканд"] },
  { code: "KG", title: "Кыргызстан", cities: ["Бишкек", "Ош"] },
  { code: "AM", title: "Армения", cities: ["Ереван"] },
  { code: "AZ", title: "Азербайджан", cities: ["Баку"] },
  { code: "GE", title: "Грузия", cities: ["Тбилиси", "Батуми"] },
  { code: "MD", title: "Молдова", cities: ["Кишинёв"] },
  { code: "PL", title: "Польша", cities: ["Warszawa", "Kraków"] },
  { code: "LT", title: "Литва", cities: ["Vilnius", "Kaunas"] },
  { code: "DE", title: "Германия", cities: ["Berlin", "München"] },
  { code: "AE", title: "ОАЭ", cities: ["Dubai", "Abu Dhabi"] }
];
var DEFAULT_NICHES = [
  { id: 0, title: "Барбершопы" }, { id: 1, title: "Салоны красоты" },
  { id: 6, title: "Маникюр и ногти" }, { id: 2, title: "Автосервисы" },
  { id: 3, title: "Стоматологии" }, { id: 4, title: "Фитнес и спортзалы" },
  { id: 7, title: "Кофейни и кафе" }, { id: 8, title: "Рестораны" },
  { id: 9, title: "Ветклиники" }, { id: 10, title: "Языковые и детские школы" },
  { id: 5, title: "Своя ниша" }
];
var CUSTOM_NICHE = 5;
var STATUS_NAMES = {
  "new": "Новый", "written": "Написал", "replied": "Ответил",
  "rejected": "Отказ", "client": "Клиент"
};
var FILTERS = [
  ["all", "Все"], ["new", "Новые"], ["written", "Написал"],
  ["replied", "Ответил"], ["rejected", "Отказ"], ["client", "Клиенты"]
];
var KINDS = [["first", "Первое"], ["short", "Короткое"], ["detailed", "Подробное"], ["call", "Звонок"], ["followup", "Повторное"]];
var TABS = [
  ["search", "Поиск", "search"], ["leads", "Лиды", "list"],
  ["scripts", "Скрипты", "doc"], ["stats", "Статистика", "chart"],
  ["faq", "Вопросы", "help"], ["admin", "Админ", "shield"]
];
var ADMIN_TABS = [["users", "Пользователи"], ["keys", "Ключи"], ["leads", "Все лиды"], ["overview", "Статистика"], ["blocked", "Чёрный список"], ["errors", "Ошибки"]];
var SUPPORT_TELEGRAM = "SUN9ISE";
var JOIN_URL = "https://t.me/m/KXcCg7quZGFh";
var NOT_FOUND = "не найдено";
var leads = [];
var S = {
  tab: "search", country: "RU", city: "", niche: 0, custom: "",
  flt: "all", count: 15, used: 0, limit: 70, filter: "all",
  admin: false, name: "", username: "", stats: {}, access: null, niches: DEFAULT_NICHES,
  users: [], editId: null, editVal: 70, loading: false,
  progress: null, requestSeq: 0, shown: 0, open: {},
  scriptNiche: 0, scripts: [], scriptEdit: null, scriptOpen: {}, scrIntro: true,
  genLead: null, genKind: "first", genVariant: 0, sheetSaved: false, sheetNiche: "",
  atab: "users", keys: [], adminLeads: [], adminQuery: "", overview: null, blocked: [], errors: null, userQuery: "",
  trialOffer: null, newKey: ""
};
var $ = function (selector) { return document.querySelector(selector); };
var esc = function (value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
  });
};
var ic = function (name, cls) {
  return '<svg class="ic' + (cls ? " " + cls : "") + '" aria-hidden="true"><use href="#i-' + esc(name) + '"/></svg>';
};
var hap = function () {
  try {
    if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
  } catch (_) {}
};
var isTrial = function () { return S.access && S.access.plan === "trial"; };
var trialOver = function () { return isTrial() && S.access.searches_left <= 0; };
var remaining = function () {
  if (isTrial()) return S.access.searches_left > 0 ? S.access.trial_leads : 0;
  return Math.max(0, S.limit - S.used);
};
var countOptions = function (rest) {
  if (isTrial()) return rest > 0 ? [S.access.trial_leads] : [];
  var values = [15, 30, 50].filter(function (value) { return value <= rest; });
  if (rest > 0 && rest < 30 && values.indexOf(rest) < 0) values.push(rest);
  return values;
};
var nicheTitle = function (id) {
  var found = S.niches.filter(function (item) { return item.id === id; })[0];
  return found ? found.title : "";
};
var leadsToView = function (lead) {
  return {
    id: lead.id,
    name: lead.name || "Без названия",
    country: lead.country || "",
    city: lead.city || "",
    phone: lead.phone || "",
    site: lead.site || "none",
    url: lead.url || "",
    c: lead.c || {},
    reasons: Array.isArray(lead.reasons) ? lead.reasons : [],
    hot: Number(lead.hot) || 0,
    status: lead.status || "new",
    need: lead.need || "",
    explain: lead.explain || "",
    info: lead.info || {},
    niche: lead.niche || "",
    source: lead.source || ""
  };
};

function toast(message) {
  var node = $("#toast");
  node.textContent = String(message || "");
  node.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(function () { node.classList.remove("show"); }, 3200);
}

function api(path, options) {
  options = options || {};
  var headers = Object.assign({}, options.headers || {}, {
    "X-Init-Data": tg && tg.initData ? tg.initData : ""
  });
  if (options.body) headers["Content-Type"] = "application/json";
  return fetch(path, Object.assign({}, options, { headers: headers }))
    .then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          var detail = data.detail;
          var text = detail;
          if (detail && typeof detail === "object" && !Array.isArray(detail)) text = detail.message;
          if (Array.isArray(detail)) text = "Проверьте введённые данные.";
          var error = new Error(text || ("Ошибка сервера: " + response.status));
          error.status = response.status;
          error.detail = detail;
          throw error;
        }
        return data;
      });
    });
}

function openLink(url) {
  try {
    if (tg && /^https:\/\/t\.me\//.test(url)) return tg.openTelegramLink(url);
    if (tg && /^https?:/.test(url)) return tg.openLink(url);
  } catch (_) {}
  window.open(url, "_blank", "noopener");
}

function copyText(text) {
  var done = function () { toast("Скопировано."); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(function () { fallbackCopy(text); });
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  var area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try { document.execCommand("copy"); toast("Скопировано."); } catch (_) { toast("Выделите текст и скопируйте вручную."); }
  document.body.removeChild(area);
}

function loadMe() {
  return api("/api/me").then(function (me) {
    S.name = me.name || "";
    S.username = me.username || "";
    S.admin = Boolean(me.is_admin);
    S.limit = Number(me.limit) || 0;
    S.used = Number(me.used) || 0;
    S.access = me.access || null;
    if (me.access && me.access.join) JOIN_URL = me.access.join;
    if (me.access && me.access.contact) SUPPORT_TELEGRAM = me.access.contact;
    if (Array.isArray(me.niches) && me.niches.length) S.niches = me.niches;
    if (Array.isArray(me.countries) && me.countries.length) COUNTRIES = me.countries;
    if (S.tab === "admin" && !S.admin) S.tab = "search";
    return me;
  });
}

function loadLeads() {
  return api("/api/leads?status=all&limit=1000").then(function (data) {
    leads = (data.leads || []).map(leadsToView);
    return leads;
  });
}

function loadStats() {
  return api("/api/stats").then(function (stats) {
    S.stats = stats || {};
    return S.stats;
  });
}

function loadScripts() {
  return api("/api/scripts?niche=" + encodeURIComponent(S.scriptNiche)).then(function (data) {
    S.scripts = data.scripts || [];
    return S.scripts;
  });
}

function refreshAll() {
  return loadMe().then(function () {
    return Promise.all([loadLeads(), loadStats()]);
  }).then(function () {
    if (S.tab === "admin" && S.admin) return loadAdmin();
  }).then(function () { render(); });
}

/* ---------- Поиск ---------- */

function accessCard() {
  if (trialOver()) return trialOfferCard(S.access.trial_message);
  if (isTrial()) {
    return '<div class="card access"><div class="row"><span>Пробный доступ</span><b>' +
      S.access.searches_left + " " + plural(S.access.searches_left, "запрос", "запроса", "запросов") +
      '</b></div><p class="muted small">До ' + S.access.trial_leads +
      ' лидов за запрос. Дальше — в команде C&amp;C Family или по ключу.</p></div>';
  }
  var rest = remaining();
  var usedPercent = S.limit ? Math.min(100, Math.round(S.used / S.limit * 100)) : 0;
  return '<div class="card"><div class="row"><span>Лимит на сегодня</span><b>' +
    S.used + " / " + S.limit + '</b></div><div class="bar"><i style="width:' +
    usedPercent + '%"></i></div><p class="muted small">Осталось ' + rest +
    '. Обновление по времени сервера.</p></div>';
}

function trialOfferCard(message) {
  var text = message || ("Пробный доступ закончился.\nЧтобы продолжить получать лиды и пользоваться Parser C&C, вступите в команду C&C Family,\nподробности можно узнать у @" + SUPPORT_TELEGRAM + ".");
  return '<div class="card offer"><p>' + esc(text) + '</p><div class="btns">' +
    '<a class="btn main" data-ext href="' + esc(JOIN_URL) + '" target="_blank" rel="noopener">' + ic("users") + "Вступить в команду</a>" +
    '<a class="btn" data-ext href="https://t.me/' + esc(SUPPORT_TELEGRAM) + '" target="_blank" rel="noopener">' + ic("plus") + "Докупить запросы</a>" +
    '<a class="btn" data-ext href="https://t.me/' + esc(SUPPORT_TELEGRAM) + '" target="_blank" rel="noopener">' + ic("send") + "Написать @" + esc(SUPPORT_TELEGRAM) + "</a></div>" +
    '<form id="key-form" class="keyform"><input name="code" placeholder="Ключ доступа CC-…" autocomplete="off" maxlength="64" aria-label="Ключ доступа">' +
    '<button class="btn" type="submit">' + ic("key") + "Ввести</button></form></div>";
}

function plural(n, one, few, many) {
  var mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

function vSearch() {
  var rest = remaining();
  var options = countOptions(rest);
  if (options.indexOf(S.count) < 0) S.count = options[0] || 0;
  var hello = S.name ? "Привет, " + esc(S.name) : "Привет";
  var cityValue = S.city ? esc(S.city) : "";
  var country = COUNTRIES.filter(function (item) { return item.code === S.country; })[0] || COUNTRIES[0];
  return '<section class="screen"><div class="hello">' + hello +
    '<small>Найди бизнесы, которым может быть нужен сайт или ТГ-бот</small></div>' +
    accessCard() +
    '<button class="fire" data-act="demand">' + ic("fire") +
    '<span>Какие ниши сейчас требуют сайт/бот?<small>Статистика по реальным проверкам парсера</small></span>' +
    ic("chev", "chev") + "</button>" +
    '<h3>Страна</h3><select id="country" aria-label="Страна">' +
    COUNTRIES.map(function (item) {
      return '<option value="' + esc(item.code) + '"' +
        (S.country === item.code ? " selected" : "") + '>' +
        esc(item.code) + " — " + esc(item.title) + "</option>";
    }).join("") +
    '</select><h3>Город или регион <span class="optional">необязательно</span></h3>' +
    '<input id="city" list="city-list" value="' + cityValue +
    '" placeholder="Любой город или пусто" autocomplete="off" maxlength="80">' +
    '<datalist id="city-list">' + (country.cities || []).map(function (name) {
      return '<option value="' + esc(name) + '"></option>';
    }).join("") + "</datalist>" +
    '<p class="muted small location-hint">Можно вписать любой город или район. Если оставить пустым — поиск пойдёт по крупным городам страны: ' +
    esc((country.cities || []).slice(0, 3).join(", ")) + (country.cities && country.cities.length > 3 ? " и другим" : "") + ".</p>" +
    '<h3>Ниша</h3><div class="chips">' +
    S.niches.map(function (item) {
      return '<button class="chip ' + (S.niche === item.id ? "on" : "") +
        '" data-act="niche" data-v="' + item.id + '">' + esc(item.title) + "</button>";
    }).join("") + "</div>" +
    (S.niche === CUSTOM_NICHE
      ? '<input id="cn" value="' + esc(S.custom) +
        '" placeholder="Слово из названия, например шиномонтаж" maxlength="80">'
      : "") +
    '<h3>Сколько</h3><div class="seg">' +
    (options.length
      ? options.map(function (value) {
        return '<button class="' + (S.count === value ? "on" : "") +
          '" data-act="count" data-v="' + value + '">' + value +
          (!isTrial() && [15, 30, 50].indexOf(value) < 0 ? " · остаток" : "") + "</button>";
      }).join("")
      : '<button disabled>' + (isTrial() ? "Пробный доступ закончился" : "Лимит исчерпан") + "</button>") +
    '</div><button class="cta" data-act="go" ' +
    (rest > 0 && S.count && !S.loading ? "" : "disabled") +
    '>Найти ' + (S.count || "") + " бизнесов</button></section>";
}

var STAGES = [
  "Собираю организации из открытых карт…",
  "Убираю дубли и уже выданные бизнесы…",
  "Открываю сайты и проверяю их…",
  "Проверяю Telegram, запись и контакты…",
  "Считаю приоритет каждого лида…"
];

function progressPercent(progress) {
  var maxChecks = progress.total * 6 + 40;
  var byChecks = progress.checked / maxChecks;
  var byFound = progress.found / Math.max(1, progress.total) * 0.92;
  return Math.min(94, Math.max(6, Math.round(Math.max(byChecks, byFound) * 100)));
}

function loadingView() {
  var progress = S.progress || { found: 0, checked: 0, total: 1 };
  return '<section class="screen center"><div class="beat"><i class="bird"></i></div>' +
    '<h2>Ищу и проверяю бизнесы</h2><p class="muted" id="pt">' +
    "Найдено " + progress.found + " из " + progress.total +
    " · проверено " + progress.checked + '</p><div class="glow"><i id="pb" style="width:' + Math.max(6, S.shown) +
    '%"></i></div><p class="muted small stage" id="pstage">' + esc(STAGES[0]) + "</p>" +
    '<p class="muted small">Каждый лид проверяется вживую, поэтому поиск занимает 1–3 минуты.</p></section>';
}

function updateLoading() {
  var progress = S.progress;
  if (!progress) return;
  var target = progressPercent(progress);
  S.shown = Math.max(S.shown, target);
  var text = $("#pt");
  var bar = $("#pb");
  var stage = $("#pstage");
  if (text) text.textContent = "Найдено " + progress.found + " из " + progress.total + " · проверено " + progress.checked;
  if (bar) bar.style.width = S.shown + "%";
  if (stage) {
    var index = progress.checked === 0 ? (S.shown < 10 ? 0 : 1) : progress.found ? 4 : (progress.checked % 2 ? 2 : 3);
    stage.textContent = STAGES[Math.min(STAGES.length - 1, index)];
  }
}

function go() {
  if (S.loading) return;
  var count = Number(S.count);
  if (!count || count > remaining()) {
    toast(isTrial() ? "Пробный доступ закончился." : "Доступно лидов на сегодня: " + remaining() + ".");
    return;
  }
  if (S.niche === CUSTOM_NICHE && !S.custom.trim()) {
    toast("Введите слово для своей ниши.");
    return;
  }

  var requestNumber = ++S.requestSeq;
  var payload = {
    country: S.country,
    city: S.city.trim(),
    niche: S.niche,
    custom: S.custom.trim(),
    flt: S.flt,
    count: count
  };
  S.loading = true;
  S.shown = 4;
  S.progress = { found: 0, checked: 0, total: count };
  render();
  var creep = setInterval(function () {
    if (!S.loading) return clearInterval(creep);
    if (S.shown < 88) { S.shown += 0.6; updateLoading(); }
  }, 1500);

  function stop(message, tab) {
    clearInterval(creep);
    S.loading = false;
    S.tab = tab || "search";
    render();
    if (message) toast(message);
  }

  api("/api/search", { method: "POST", body: JSON.stringify(payload) })
    .then(function (result) {
      S.progress.total = Number(result.count) || count;
      function poll() {
        if (requestNumber !== S.requestSeq) return;
        api("/api/jobs/" + encodeURIComponent(result.job_id)).then(function (job) {
          S.progress = {
            found: Number(job.found) || 0,
            checked: Number(job.checked) || 0,
            total: Number(job.total) || count
          };
          updateLoading();
          if (job.status === "done") {
            S.shown = 100;
            updateLoading();
            S.trialOffer = job.trial_over || null;
            return Promise.all([loadMe(), loadLeads(), loadStats()]).then(function () {
              setTimeout(function () {
                stop("Поиск завершён. Новых лидов: " + (job.found || 0) + ".", "leads");
                S.filter = "all";
                if (S.trialOffer) showTrialOffer(S.trialOffer);
              }, 500);
            });
          }
          if (job.status === "error") {
            stop(job.error || "Поиск завершился с ошибкой.");
            return;
          }
          setTimeout(poll, 1200);
        }).catch(function (error) { stop(error.message); });
      }
      poll();
    })
    .catch(function (error) {
      if (error.detail && error.detail.code === "trial_over") {
        stop("");
        loadMe().then(function () { render(); showTrialOffer(error.detail); });
        return;
      }
      stop(error.message);
    });
}

function showTrialOffer(detail) {
  openSheet('<div class="top"><h2>C&amp;C Family</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' +
    ic("x") + "</button></div>" + trialOfferCard(detail && detail.message));
}

/* ---------- Ниши со спросом ---------- */

function showDemand() {
  var head = '<div class="top"><h2>Каким нишам сейчас нужен сайт или бот</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' + ic("x") + "</button></div>";
  openSheet(head + '<div class="dots"><i></i><i></i><i></i></div>');
  api("/api/demand?country=" + encodeURIComponent(S.country)).then(function (data) {
    var items = data.items || [];
    var note = data.source === "ai"
      ? "Оценка нейросети по нашим нишам для выбранной страны. Обновляется раз в сутки."
      : (data.note || "Базовая оценка по опыту продаж сайтов и ботов.");
    setSheetBody(head + '<p class="lead-note">' + esc(note) + "</p>" +
      items.map(function (item, index) {
        return '<div class="dm"><div class="dm-top"><span class="dm-n">' + (index + 1) + '</span><b>' + esc(item.niche) +
          '</b><span class="score">' + esc(item.score) + "/10</span></div>" +
          '<p class="dm-why">' + esc(item.why) + "</p>" +
          (item.offer ? '<p class="dm-offer"><span>Что предложить:</span> ' + esc(item.offer) + "</p>" : "") +
          (item.id != null ? '<button class="btn small" data-act="pickniche" data-v="' + esc(item.id) + '">' + ic("search") + "Искать в этой нише</button>" : "") +
          "</div>";
      }).join(""));
  }).catch(function (error) {
    closeSheet();
    toast(error.message);
  });
}

/* ---------- Лиды ---------- */

function safeHttpLink(value) {
  try {
    var url = new URL(String(value || ""));
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch (_) { return ""; }
}

function leadPhones(lead) {
  var info = lead.info || {};
  var list = Array.isArray(info.phones) && info.phones.length ? info.phones : (lead.phone ? [lead.phone] : []);
  return list.filter(function (value, index) { return value && list.indexOf(value) === index; });
}

function telLink(phone, cls) {
  var dialable = String(phone || "").replace(/[^\d+]/g, "");
  return '<a class="' + (cls || "tel") + '" href="tel:' + esc(dialable) + '">' + ic("phone") + esc(phone) + "</a>";
}

function leadCard(lead, index) {
  var status = lead.status || "new";
  var phones = leadPhones(lead);
  var open = Boolean(S.open[lead.id]);
  var c = lead.c || {};
  var map = safeHttpLink(c.map || "");
  var address = c.address || (lead.info && lead.info.address) || "";
  return '<article class="card lead" style="--i:' + index + '">' +
    '<b class="lname">' + esc(lead.name) + "</b>" +
    '<p class="meta">' + esc(lead.niche || "") + (lead.niche ? " · " : "") + esc(lead.city) + "</p>" +
    (address ? '<p class="addr">' + esc(address) + "</p>" : "") +
    '<div class="phones">' + (phones.length
      ? telLink(phones[0]) + (phones.length > 1
        ? '<button class="more-ph' + (open ? " on" : "") + '" data-act="phones" data-id="' + encodeURIComponent(lead.id) +
          '" aria-label="Другие номера">+' + (phones.length - 1) + ic("chev", "down") + "</button>"
        : "")
      : '<span class="meta">Телефон не указан на карте</span>') + "</div>" +
    (open && phones.length > 1 ? '<div class="ph-list">' + phones.slice(1).map(function (phone) { return telLink(phone, "tel alt"); }).join("") + "</div>" : "") +
    '<div class="acts">' +
    (map ? '<a class="btn main" data-ext href="' + esc(map) + '" target="_blank" rel="noopener">' + ic("pin") + "Открыть на карте</a>" : "") +
    '<button class="btn" data-act="leadscript" data-id="' + encodeURIComponent(lead.id) + '">' + ic("spark") + "Скрипт</button></div>" +
    '<div class="st">' + ["written", "replied", "rejected", "client"].map(function (key) {
      return '<button class="' + (status === key ? "on" : "") +
        '" data-act="status" data-id="' + encodeURIComponent(lead.id) +
        '" data-v="' + key + '">' + STATUS_NAMES[key] + "</button>";
    }).join("") + "</div></article>";
}

function vLeads() {
  var filtered = leads.filter(function (lead) {
    return S.filter === "all" || lead.status === S.filter;
  });
  return '<section class="screen"><div class="top"><h2>Лиды <small>' +
    esc(S.stats.found == null ? leads.length : S.stats.found) +
    '</small></h2><button class="icon-btn" data-act="export" aria-label="Скачать Excel">' +
    ic("download") + "</button></div>" +
    '<div class="chips scroll">' + FILTERS.map(function (item) {
      return '<button class="chip ' + (S.filter === item[0] ? "on" : "") +
        '" data-act="filter" data-v="' + item[0] + '">' + item[1] + "</button>";
    }).join("") + "</div>" +
    (isTrial() && leads.length ? trialMini() : "") +
    (filtered.length
      ? filtered.map(leadCard).join("")
      : '<div class="empty">' + ic("list") + "<p>" +
        (leads.length ? "В этом фильтре пока пусто" : "Здесь пока пусто") + "</p></div>") +
    (leads.length >= 1000
      ? '<p class="muted small" style="text-align:center">Показаны последние 1000 лидов. Полный список можно выгрузить в Excel.</p>'
      : "") +
    (leads.length ? '<p class="muted small srcnote">Данные организаций: <a data-ext href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a>, сайты самих компаний.</p>' : "") +
    "</section>";
}

function trialMini() {
  if (!trialOver()) return "";
  return '<div class="card offer"><div class="row"><b>Пробный доступ закончился</b></div>' +
    '<p class="muted small">Лиды остаются у вас. Чтобы искать дальше — вступите в C&amp;C Family.</p>' +
    '<div class="btns"><button class="btn main" data-act="offer">Подробнее</button></div></div>';
}

function generateLeadScript(lead, kind, variant) {
  kind = kind || "first";
  variant = variant || 0;
  S.genLead = lead.id;
  S.genKind = kind;
  S.genVariant = variant;
  var head = '<div class="top"><h2>Скрипт для «' + esc(lead.name) + '»</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' +
    ic("x") + '</button></div><div class="chips scroll kinds">' + KINDS.map(function (item) {
      return '<button class="chip ' + (kind === item[0] ? "on" : "") + '" data-act="leadkind" data-id="' +
        encodeURIComponent(lead.id) + '" data-v="' + item[0] + '">' + item[1] + "</button>";
    }).join("") + "</div>";
  openSheet(head + '<div class="dots"><i></i><i></i><i></i></div><p class="meta center-text">Пишу скрипт для этого бизнеса…</p>');
  api("/api/leads/" + encodeURIComponent(lead.id) + "/script", {
    method: "POST", body: JSON.stringify({ kind: kind, variant: variant })
  }).then(function (result) {
    S.sheetText = result.text || "";
    S.sheetSaved = false;
    S.sheetNiche = lead.niche;
    setSheetBody(head + '<div class="card"><pre id="gen-text">' + esc(result.text) + "</pre></div>" +
      '<p class="meta">' + (result.note ? esc(result.note) + " " : "") + "Перед отправкой прочитайте и при необходимости поправьте.</p>" +
      genTools("leadmore", kind));
  }).catch(function (error) {
    closeSheet();
    toast(error.message);
  });
}

function genTools(moreAction, kind) {
  return '<div class="tools"><button class="main" data-act="copygen">' + ic("copy") + "Копировать</button>" +
    '<button data-act="' + moreAction + '" data-v="' + kind + '">' + ic("spark") + "Ещё вариант</button>" +
    '<button id="save-gen" data-act="savegen" data-v="' + kind + '"' + (S.sheetSaved ? " disabled" : "") + ">" +
    ic("doc") + (S.sheetSaved ? "Сохранено" : "Сохранить в мои скрипты") + "</button></div>";
}

/* ---------- Скрипты ---------- */

function vScripts() {
  var niches = S.niches.filter(function (item) { return item.id !== CUSTOM_NICHE; });
  var list = S.scripts || [];
  return '<section class="screen"><h2>Скрипты</h2>' +
    '<details class="intro"' + (S.scrIntro ? " open" : "") + ' data-intro="scripts"><summary>' + ic("info") + "Что можно делать на этой странице</summary>" +
    '<div class="intro-body">' +
    "<p>Здесь готовые тексты, с которых удобно начать общение с бизнесом.</p>" +
    '<ul class="steps">' +
    "<li><b>Выберите нишу</b> — для каждой есть 5 скриптов: первое сообщение, короткое, подробное, звонок и повторное.</li>" +
    "<li><b>Скопируйте</b> и замените [Название] и [Ваше имя] на свои данные.</li>" +
    "<li><b>Измените</b> любой скрипт под себя — он сохранится как ваш.</li>" +
    "<li><b>Сгенерируйте новый</b> вариант, если нужен другой текст.</li>" +
    "</ul>" +
    '<p class="meta">Для конкретного бизнеса нажмите «Скрипт» в карточке лида — текст напишется с его названием.</p>' +
    (S.admin ? '<p class="meta">Вы администратор: правка стандартного скрипта меняет его для всех.</p>' : "") +
    "</div></details>" +
    '<h3>Ниша</h3><select id="sniche" aria-label="Ниша">' + niches.map(function (item) {
      return '<option value="' + item.id + '"' + (S.scriptNiche === item.id ? " selected" : "") + ">" + esc(item.title) + "</option>";
    }).join("") + "</select>" +
    '<div class="card scr-list">' + (list.length ? list.map(scriptItem).join("") : '<div class="dots"><i></i><i></i><i></i></div>') + "</div>" +
    '<div class="card"><h3>Сгенерировать новый</h3><p class="meta">Новый вариант для ниши «' +
    esc(nicheTitle(S.scriptNiche)) + '». Каждое нажатие — другой текст.</p><div class="tools">' + KINDS.map(function (item) {
      return '<button data-act="genniche" data-v="' + item[0] + '">' + ic("spark") + item[1] + "</button>";
    }).join("") + "</div></div></section>";
}

function scriptItem(item) {
  var editing = S.scriptEdit === item.id;
  var open = Boolean(S.scriptOpen[item.id]);
  var kindName = (KINDS.filter(function (k) { return k[0] === item.kind; })[0] || [0, item.kind])[1];
  if (editing) {
    return '<div class="scr"><form id="script-form" data-id="' + item.id + '" data-kind="' + esc(item.kind) + '" class="form">' +
      '<input name="title" value="' + esc(item.title) + '" maxlength="80" required aria-label="Название">' +
      '<textarea name="body" rows="9" maxlength="4000" required>' + esc(item.body) + "</textarea>" +
      '<div class="tools"><button class="main" type="submit">Сохранить</button><button type="button" data-act="scancel">Отмена</button></div>' +
      (!item.own && !S.admin ? '<p class="meta">Сохранится ваша копия, стандартный скрипт останется.</p>' : "") +
      "</form></div>";
  }
  return '<div class="scr"><div class="scr-head"><b>' + esc(item.title) + '</b><span class="tag' + (item.own ? " own" : "") + '">' +
    (item.own ? "Мой" : esc(kindName)) + "</span></div>" +
    '<p class="scr-text' + (open ? "" : " clamp") + '">' + esc(item.body) + "</p>" +
    '<div class="tools"><button class="main" data-act="scopy" data-id="' + item.id + '">' + ic("copy") + "Копировать</button>" +
    '<button data-act="sedit" data-id="' + item.id + '">' + ic("edit") + "Изменить</button>" +
    '<button data-act="sopen" data-id="' + item.id + '">' + (open ? "Свернуть" : "Читать полностью") + "</button>" +
    (item.own || S.admin ? '<button data-act="sdel" data-id="' + item.id + '">' + ic("trash") + "Удалить</button>" : "") +
    "</div></div>";
}

function generateNicheScript(kind, variant) {
  var title = nicheTitle(S.scriptNiche);
  variant = variant || 1;
  S.genVariant = variant;
  var head = '<div class="top"><h2>Новый скрипт: ' + esc(title) + '</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' + ic("x") + "</button></div>";
  openSheet(head + '<div class="dots"><i></i><i></i><i></i></div>');
  api("/api/scripts/generate", {
    method: "POST", body: JSON.stringify({ niche: S.scriptNiche, kind: kind, variant: variant })
  }).then(function (result) {
    S.sheetText = result.text || "";
    S.sheetSaved = false;
    S.sheetNiche = title;
    setSheetBody(head + '<div class="card"><pre>' + esc(result.text) + "</pre></div>" +
      (result.note ? '<p class="meta">' + esc(result.note) + "</p>" : "") + genTools("nichemore", kind));
  }).catch(function (error) { closeSheet(); toast(error.message); });
}

function saveGenerated(kind) {
  if (S.sheetSaved) return;
  var niche = (S.niches.filter(function (item) { return item.title === S.sheetNiche; })[0] || {}).id;
  if (niche == null || niche === CUSTOM_NICHE) niche = S.scriptNiche;
  var kindName = (KINDS.filter(function (k) { return k[0] === kind; })[0] || [0, "Скрипт"])[1];
  S.sheetSaved = true;
  var button = $("#save-gen");
  if (button) { button.disabled = true; button.innerHTML = ic("doc") + "Сохранено"; }
  api("/api/scripts", {
    method: "POST",
    body: JSON.stringify({ niche: niche, kind: kind, title: kindName + " — мой вариант", body: S.sheetText || "" })
  }).then(function () {
    toast("Сохранено во вкладке «Скрипты».");
    if (S.scriptNiche === niche) loadScripts().then(function () { if (S.tab === "scripts") render(true); });
  }).catch(function (error) {
    S.sheetSaved = false;
    if (button) { button.disabled = false; button.innerHTML = ic("doc") + "Сохранить в мои скрипты"; }
    toast(error.message);
  });
}

/* ---------- Статистика и FAQ ---------- */

function vStats() {
  var stats = S.stats || {};
  var total = Number(stats.found) || 0;
  var contacted = Number(stats.contacted) || 0;
  var replied = Number(stats.replied) || 0;
  var clients = Number(stats.clients) || 0;
  var rows = [["Найдено", total], ["Связались", contacted], ["Ответили", replied], ["Клиенты", clients]];
  var percentage = function (value) { return total ? Math.round(value / total * 100) : 0; };
  return '<section class="screen"><h2>Статистика</h2><div class="grid">' +
    rows.map(function (row) {
      return '<div class="card tile"><small class="muted">' + row[0] +
        '</small><b class="num" data-to="' + row[1] + '">' + row[1] + "</b></div>";
    }).join("") + '</div><div class="card"><h3>Воронка</h3>' +
    rows.map(function (row) {
      return '<div class="fn"><span>' + row[0] + '</span><div class="bar"><i style="width:' +
        percentage(row[1]) + '%"></i></div><em>' + percentage(row[1]) + "%</em></div>";
    }).join("") + '</div><div class="card"><div class="row"><span>Ответили от найденных</span><b>' +
    percentage(replied) + '%</b></div><div class="row g"><span>Клиенты от найденных</span><b>' +
    percentage(clients) + "%</b></div></div>" +
    '<p class="muted small">Статистика показывает только отмеченные вручную результаты. Она не предсказывает будущие продажи.</p></section>';
}

function faqItem(question, answer) {
  return "<details><summary>" + question + "</summary><div class=\"faq-a\">" + answer + "</div></details>";
}

function vFaq() {
  var steps = [
    ["Выберите страну, город и нишу", "Город можно не указывать — тогда поиск пройдёт по крупным городам страны."],
    ["Нажмите «Найти»", "Парсер найдёт бизнесы на карте и проверит, что у них есть телефон. Каждый бизнес достаётся только вам."],
    ["Откройте бизнес на карте", "Кнопка «Открыть на карте» покажет его карточку: сайт, соцсети, отзывы и часы работы."],
    ["Напишите или позвоните", "Нажмите «Скрипт» — получите готовый текст с названием бизнеса."],
    ["Отмечайте результат", "Статусы «Написал», «Ответил», «Отказ», «Клиент» помогают не потеряться и видеть свою воронку."]
  ];
  var keys = [
    ["Как найти клиентов?", "Выберите нишу и город и нажмите «Найти». Начните с ниш из кнопки <b>«Какие ниши требуют сайт/бот?»</b> на главной — там самые подходящие."],
    ["Как связаться с бизнесом?", "У каждого лида есть телефон из карточки на карте. Если номеров несколько, нажмите на <b>стрелочку</b> рядом с номером. Сайт, соцсети и отзывы смотрите по кнопке <b>«Открыть на карте»</b>."],
    ["Могу ли я получить того же клиента, что и другой участник?", "Нет. Каждый бизнес закрепляется <b>только за одним человеком</b>. Повторные поиски тоже не выдают уже полученных."],
    ["Что такое пробный доступ?", "Каждому доступен <b>1 запрос до 10 лидов</b>. Если ничего не нашлось, запрос не списывается."],
    ["Как получить полный доступ?", "Вступите в команду C&amp;C Family — подробности у @SUN9ISE. Если вам выдали ключ, введите его на главной или отправьте боту: <b>/key КОД</b>."],
    ["Что писать бизнесу?", "Во вкладке <b>«Скрипты»</b> есть готовые тексты по нишам. В карточке лида кнопка «Скрипт» пишет текст под конкретный бизнес. «Ещё вариант» даёт другой текст."],
    ["Какую нишу выбрать?", "Кнопка с огоньком на главной показывает, каким нишам сейчас больше всего нужен сайт или бот и что им предложить."],
    ["Зачем отмечать статусы?", "Чтобы видеть, кому уже написали, кто ответил и кто стал клиентом. Это же видно во вкладке «Статистика»."],
    ["Как выгрузить лиды?", "На вкладке «Лиды» нажмите кнопку загрузки — Excel-файл придёт в чат с ботом."],
    ["Что такое лимит?", "Для участников — сколько лидов можно получить за день. Если поиск нашёл меньше, остаток возвращается."],
    ["В каких странах работает?", "14 стран: Россия, Украина, Беларусь, Казахстан, Узбекистан, Кыргызстан, Армения, Азербайджан, Грузия, Молдова, Польша, Литва, Германия, ОАЭ. Можно вписать любой город."],
    ["Номер не отвечает или данные устарели", "Данные берутся из открытых карт, и бизнесы иногда меняют номера. Откройте бизнес на карте — там обычно актуальный телефон."],
    ["Откуда берутся данные?", "Из открытых карт: © OpenStreetMap contributors (лицензия ODbL), а также Geoapify."]
  ];
  return '<section class="screen"><h2>Вопросы</h2>' +
    '<div class="card howto"><h3>Как пользоваться</h3><ol class="howto-steps">' +
    steps.map(function (step) { return "<li><b>" + esc(step[0]) + "</b><span>" + esc(step[1]) + "</span></li>"; }).join("") +
    "</ol></div>" +
    '<div class="card faq"><h3>Частые вопросы</h3>' +
    keys.map(function (item) { return faqItem(esc(item[0]), item[1]); }).join("") +
    "</div><a class=\"contact\" data-ext href=\"https://t.me/" + esc(SUPPORT_TELEGRAM) +
    "\" target=\"_blank\" rel=\"noopener\">" + ic("send") +
    "Написать @" + esc(SUPPORT_TELEGRAM) + "</a>" +
    '<p class="meta center-text" style="margin:10px 0 4px">Поддержка</p></section>';
}

/* ---------- Админ ---------- */

function loadAdmin() {
  if (!S.admin) return Promise.reject(new Error("Только для администратора."));
  var loaders = {
    users: function () { return api("/api/admin/users").then(function (d) { S.users = d.users || []; }); },
    keys: function () { return api("/api/admin/keys").then(function (d) { S.keys = d.keys || []; }); },
    leads: function () {
      return api("/api/admin/leads?q=" + encodeURIComponent(S.adminQuery)).then(function (d) { S.adminLeads = (d.leads || []).map(function (l) { var v = leadsToView(l); v.owner = l.owner; return v; }); });
    },
    overview: function () { return api("/api/admin/overview").then(function (d) { S.overview = d; }); },
    blocked: function () { return api("/api/admin/blocked").then(function (d) { S.blocked = d.items || []; }); },
    errors: function () { return api("/api/admin/overview").then(function (d) { S.errors = d.errors; S.overview = d; }); }
  };
  return (loaders[S.atab] || loaders.users)();
}

function userRow(user) {
  var editing = S.editId === user.id;
  var badge = user.banned ? '<span class="badge b">Бан</span>' :
    user.plan === "member" ? '<span class="badge m">' + (user.is_admin ? "Владелец" : "Участник") + "</span>" :
    '<span class="badge">Проба ' + user.trial_used + "/" + (1 + Number(user.bonus || 0)) + "</span>";
  return '<div class="usr"><div class="row"><b>' + esc(user.n) + "</b>" + badge + "</div>" +
    '<p class="muted small">ID ' + esc(user.id) + (user.plan === "member" ? " · сегодня " + user.t + "/" + user.lim : " · осталось запросов " + esc(user.trial_left)) +
    " · лидов " + user.f + " · клиенты " + user.k + (user.bonus ? " · бонус " + user.bonus : "") + "</p>" +
    (user.is_admin ? "" : '<div class="urow">' +
      '<button data-act="access" data-id="' + user.id + '" data-v="' + (user.approved ? "0" : "1") + '">' + (user.approved ? "Закрыть доступ" : "Выдать доступ") + "</button>" +
      '<button data-act="edit" data-id="' + user.id + '">' + ic("edit") + " Лимит</button>" +
      '<button data-act="bonus" data-id="' + user.id + '" data-v="1">+1 запрос</button>' +
      '<button data-act="bonus" data-id="' + user.id + '" data-v="5">+5</button>' +
      '<button data-act="ban" data-id="' + user.id + '" data-v="' + (user.banned ? "0" : "1") + '">' + (user.banned ? "Разбанить" : "Забанить") + "</button></div>") +
    (editing
      ? '<div class="edit"><div class="row"><span class="muted small">Дневной лимит: <b>' +
        S.editVal + '</b></span><div class="step"><button data-act="limd" data-v="-10" aria-label="Меньше">−</button>' +
        '<button data-act="limd" data-v="10" aria-label="Больше">+</button></div></div>' +
        '<div class="chips">' + [0, 70, 100, 150, 200, 500].map(function (value) {
          return '<button class="chip ' + (S.editVal === value ? "on" : "") + '" data-act="limset" data-v="' + value + '">' + value + "</button>";
        }).join("") + '</div><div class="row g"><button class="ghost" data-act="limcancel">Отмена</button><button class="ghost go" data-act="limsave">Сохранить</button></div></div>'
      : "") + "</div>";
}

function adminUsers() {
  var query = S.userQuery.trim().toLowerCase();
  var users = (S.users || []).filter(function (user) {
    return !query || String(user.n).toLowerCase().indexOf(query) >= 0 || String(user.id).indexOf(query) >= 0;
  });
  var members = S.users.filter(function (u) { return u.plan === "member"; }).length;
  var trials = S.users.filter(function (u) { return u.plan === "trial" && !u.banned; }).length;
  var banned = S.users.filter(function (u) { return u.banned; }).length;
  return '<div class="grid">' + [["Участников", members], ["На пробе", trials], ["Забанено", banned], ["Всего", S.users.length]].map(function (row) {
      return '<div class="card tile"><small class="muted">' + row[0] + '</small><b class="num" data-to="' + row[1] + '">' + row[1] + "</b></div>";
    }).join("") + "</div>" +
    '<div class="card"><h3>Выдать полный доступ</h3><form id="grant-form" class="form"><div class="two">' +
    '<input name="query" required placeholder="@username / ID" aria-label="Пользователь">' +
    '<input name="limit" type="number" min="1" max="5000" placeholder="Лимит/день" aria-label="Лимит лидов в день"></div>' +
    '<button class="btn main" type="submit">' + ic("plus") + "Выдать</button></form>" +
    '<p class="muted small">По @username — если человек уже нажимал /start. Иначе — по ID или создайте ключ.</p></div>' +
    '<div class="card"><h3>Пользователи</h3><input id="user-q" value="' + esc(S.userQuery) + '" placeholder="Поиск по @username или ID" autocomplete="off">' +
    (users.length ? users.map(userRow).join("") : '<p class="muted" style="margin-top:10px">Никого не найдено.</p>') + "</div>" +
    '<div class="card"><h3>Рассылка</h3><form id="broadcast-form"><textarea name="text" maxlength="4000" required rows="4" placeholder="Текст сообщения"></textarea>' +
    '<button class="btn" type="submit" style="width:100%;margin-top:8px">' + ic("send") + "Отправить всем, кроме забаненных</button></form></div>";
}

function adminKeys() {
  return '<div class="card"><h3>Новый ключ доступа</h3><form id="key-create" class="form">' +
    '<label>Для кого (необязательно)<input name="for_user" placeholder="@username или ID" maxlength="64"></label>' +
    '<div class="two"><label>Лимит лидов в день<input name="limit" type="number" min="0" max="5000" value="70"></label>' +
    '<label>Бонус запросов<input name="bonus" type="number" min="0" max="1000" value="0"></label></div>' +
    '<div class="two"><label>Активаций<input name="uses" type="number" min="1" max="1000" value="1"></label>' +
    '<label>Заметка<input name="note" maxlength="120" placeholder="например, оплатил"></label></div>' +
    '<button class="btn main" type="submit">' + ic("key") + "Создать ключ</button></form>" +
    (S.newKey ? '<div class="card" style="margin-bottom:0"><p class="muted small">Ключ создан. Пользователь вводит его в приложении или командой /key.</p><div class="row g"><span class="code">' + esc(S.newKey) +
      '</span><button class="ghost" style="flex:none" data-act="copykey" data-v="' + esc(S.newKey) + '">' + ic("copy") + "Копировать</button></div></div>" : "") +
    "</div>" +
    '<div class="card"><h3>Ключи</h3>' + (S.keys.length ? S.keys.map(function (key) {
      return '<div class="usr"><div class="row"><span class="code">' + esc(key.code) + '</span><button class="chip mini" data-act="delkey" data-v="' + esc(key.code) + '">' + ic("trash") + "</button></div>" +
        '<p class="muted small">' + (key.for_user ? "для " + esc(key.for_user) + " · " : "для любого · ") +
        (key.daily_limit ? "лимит " + key.daily_limit + " · " : "") + (key.bonus ? "+" + key.bonus + " запросов · " : "") +
        "осталось активаций " + key.uses_left + (key.used_by ? " · активировали: " + esc(key.used_by) : "") +
        (key.note ? " · " + esc(key.note) : "") + "</p></div>";
    }).join("") : '<p class="muted">Ключей пока нет.</p>') + "</div>";
}

function adminLeads() {
  return '<div class="card"><form id="aleads-form" class="keyform"><input name="q" value="' + esc(S.adminQuery) +
    '" placeholder="Название, город, телефон или @username"><button class="btn" type="submit">' + ic("search") + "</button></form></div>" +
    (S.adminLeads.length ? S.adminLeads.map(function (lead) {
      return '<div class="card"><div class="row"><b>' + esc(lead.name) + '</b><span class="badge">' + esc(lead.hot) + "</span></div>" +
        '<p class="muted small">' + esc(lead.country) + " · " + esc(lead.city) + (lead.niche ? " · " + esc(lead.niche) : "") +
        " · " + esc(STATUS_NAMES[lead.status] || lead.status) + " · у " + esc(lead.owner) + "</p>" +
        (lead.phone ? '<p class="small">' + esc(lead.phone) + "</p>" : "") +
        (lead.explain ? '<p class="why">' + esc(lead.explain) + "</p>" : "") +
        '<div class="urow"><button data-act="blocklead" data-id="' + lead.id + '">' + ic("ban") + " В чёрный список</button></div></div>";
    }).join("") : '<div class="empty"><p>Лидов не найдено</p></div>');
}

function table(rows, headers) {
  if (!rows || !rows.length) return '<p class="muted">Пока нет данных.</p>';
  return '<div style="overflow-x:auto"><table class="tbl"><tr>' + headers.map(function (h) { return "<th>" + h + "</th>"; }).join("") + "</tr>" +
    rows.map(function (row) {
      return "<tr><td>" + esc(row.name) + "</td><td>" + esc(row.leads) + "</td><td>" + esc(row.clients || 0) + "</td><td>" + esc(row.avg || 0) + "</td></tr>";
    }).join("") + "</table></div>";
}

function adminOverview() {
  var o = S.overview;
  if (!o) return '<div class="dots"><i></i><i></i><i></i></div>';
  return '<div class="grid">' + [["Пользователей", o.users.total], ["Участников", o.users.members], ["Пробу использовали", o.users.trial_used], ["Пробу не начали", o.users.trial_left],
      ["Лидов выдано", o.leads.total], ["Связались", o.leads.contacted], ["Клиентов", o.leads.clients], ["Забанено", o.users.banned]].map(function (row) {
      return '<div class="card tile"><small class="muted">' + row[0] + '</small><b class="num" data-to="' + (row[1] || 0) + '">' + (row[1] || 0) + "</b></div>";
    }).join("") + "</div>" +
    '<div class="card"><h3>По нишам</h3>' + table(o.niches, ["Ниша", "Лиды", "Клиенты", "Приор."]) + "</div>" +
    '<div class="card"><h3>По городам</h3>' + table(o.cities, ["Город", "Лиды", "Клиенты", "Приор."]) + "</div>" +
    '<div class="card"><h3>Внешние сервисы</h3><p class="muted small">Geoapify сегодня: ' + esc(o.api.geoapify_day) +
    " кредитов · нейросеть сегодня: " + esc(o.api.ai_day) + " запросов · Google за месяц: " + esc(o.api.google_month) + "</p></div>";
}

function adminBlocked() {
  return '<div class="card"><h3>Добавить бизнес</h3><form id="block-form" class="keyform"><input name="text" required placeholder="Телефон, сайт, email или @telegram">' +
    '<button class="btn" type="submit">' + ic("ban") + "</button></form>" +
    '<p class="muted small">Такой бизнес больше никому не выдаётся. Лид можно добавить и из вкладки «Все лиды».</p></div>' +
    '<div class="card"><h3>Чёрный список</h3>' + (S.blocked.length ? S.blocked.map(function (item) {
      return '<div class="usr"><div class="row"><b>' + esc(item.label) + '</b><button class="chip mini" data-act="unblock" data-v="' + esc(item.label) + '">Убрать</button></div></div>';
    }).join("") : '<p class="muted">Пусто.</p>') + "</div>";
}

function adminErrors() {
  var errors = S.errors || { recent: [], day: {} };
  var names = { osm: "OpenStreetMap", geoapify: "Geoapify", google: "Google", gemini: "Нейросеть" };
  var day = Object.keys(errors.day || {});
  return '<div class="card"><h3>За сутки</h3>' + (day.length ? day.map(function (key) {
      return '<div class="row"><span>' + esc(names[key] || key) + "</span><b>" + esc(errors.day[key]) + "</b></div>";
    }).join("") : '<p class="muted">Ошибок нет — все источники отвечают.</p>') + "</div>" +
    '<div class="card"><h3>Последние</h3>' + (errors.recent.length ? errors.recent.map(function (item) {
      return '<div class="err"><b>' + esc(names[item.provider] || item.provider) + '</b> <span class="muted small">' +
        esc(new Date(item.created_at * 1000).toLocaleString("ru-RU")) + "</span><p class=\"muted small\">" + esc(item.message) + "</p></div>";
    }).join("") : '<p class="muted">Пусто.</p>') + "</div>" +
    '<p class="muted small">Ошибка одного источника не ломает поиск: остальные продолжают работать.</p>';
}

function vAdmin() {
  if (!S.admin) return '<section class="screen"><div class="card empty">Нет доступа.</div></section>';
  var views = { users: adminUsers, keys: adminKeys, leads: adminLeads, overview: adminOverview, blocked: adminBlocked, errors: adminErrors };
  return '<section class="screen"><h2>Админ-панель</h2><div class="atabs">' + ADMIN_TABS.map(function (item) {
      return '<button class="chip ' + (S.atab === item[0] ? "on" : "") + '" data-act="atab" data-v="' + item[0] + '">' + item[1] + "</button>";
    }).join("") + "</div>" + (views[S.atab] || adminUsers)() + "</section>";
}

/* ---------- Отрисовка ---------- */

function countUp(element, value) {
  var start = performance.now();
  (function frame(now) {
    var progress = Math.min(1, (now - start) / 700);
    element.textContent = Math.round(value * (1 - Math.pow(1 - progress, 3)));
    if (progress < 1) requestAnimationFrame(frame);
  })(start);
}

function render(keepScroll) {
  var oldScroll = window.scrollY;
  var views = {
    "search": S.loading ? loadingView : vSearch,
    "leads": vLeads,
    "scripts": vScripts,
    "stats": vStats,
    "faq": vFaq,
    "admin": vAdmin
  };
  if (S.tab === "admin" && !S.admin) S.tab = "search";
  $("#app").classList.toggle("still", Boolean(keepScroll));
  $("#app").innerHTML = views[S.tab]();
  $("#tabs").innerHTML = TABS.filter(function (tab) {
    return tab[0] !== "admin" || S.admin;
  }).map(function (tab) {
    return '<button class="' + (S.tab === tab[0] ? "on" : "") +
      '" data-act="tab" data-v="' + tab[0] + '">' + ic(tab[2]) + "<span>" + tab[1] + "</span></button>";
  }).join("");
  document.querySelectorAll(".num").forEach(function (element) {
    var value = Number(element.dataset.to) || 0;
    if (keepScroll) element.textContent = String(value);
    else countUp(element, value);
  });
  window.scrollTo(0, keepScroll ? oldScroll : 0);
}

function openSheet(html) {
  var sheet = $("#sheet");
  sheet.innerHTML = '<div class="sheet">' + html + "</div>";
  sheet.classList.add("show");
  document.body.style.overflow = "hidden";
}

function setSheetBody(html) {
  var inner = $("#sheet .sheet");
  if (inner) inner.innerHTML = html;
  else openSheet(html);
}

function closeSheet() {
  var sheet = $("#sheet");
  sheet.classList.remove("show");
  sheet.innerHTML = "";
  document.body.style.overflow = "";
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $("#theme").innerHTML = ic(theme === "dark" ? "sun" : "moon");
  var background = theme === "dark" ? "#151619" : "#f3f3f4";
  document.querySelector('meta[name="theme-color"]').content = background;
  try {
    if (tg) {
      tg.setHeaderColor(background);
      tg.setBackgroundColor(background);
    }
  } catch (_) {}
}

function saveLeadStatus(lead, nextStatus) {
  var previous = lead.status;
  lead.status = nextStatus;
  render(true);
  api("/api/leads/" + encodeURIComponent(lead.id) + "/status", {
    method: "POST", body: JSON.stringify({ status: nextStatus })
  }).then(function () {
    return loadStats();
  }).then(function () {
    if (S.tab === "leads") render(true);
    toast("Статус лида обновлён.");
  }).catch(function (error) {
    lead.status = previous;
    render(true);
    toast(error.message);
  });
}

function adminAction(path, body, message) {
  return api(path, { method: "POST", body: JSON.stringify(body) }).then(function (result) {
    return loadAdmin().then(function () {
      render(true);
      toast((result && result.message) || message);
    });
  }).catch(function (error) { toast(error.message); });
}

function findLead(id) {
  return leads.filter(function (item) { return String(item.id) === String(id); })[0];
}

function clickHandler(event) {
  var target = event.target;
  if (target.closest(".hot") == null) {
    document.querySelectorAll(".hot.open").forEach(function (node) { node.classList.remove("open"); });
  }
  if (target.id === "sheet") { closeSheet(); return; }

  if (target.closest("#theme")) {
    hap();
    setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    return;
  }

  var link = target.closest(".ct a,.contact,a[data-ext]");
  if (link && tg) {
    if (/^https?:/.test(link.href)) {
      event.preventDefault();
      openLink(link.href);
    }
    return;
  }

  var button = target.closest("[data-act]");
  if (!button || button.disabled) return;
  hap();
  var action = button.dataset.act;
  var value = button.dataset.v;
  var id = button.dataset.id ? decodeURIComponent(button.dataset.id) : "";

  if (action === "tab") {
    S.tab = value;
    if (S.tab === "admin") {
      render();
      loadAdmin().then(function () { render(true); }).catch(function (error) { S.tab = "search"; render(); toast(error.message); });
    } else if (S.tab === "scripts") {
      if (S.scriptNiche === CUSTOM_NICHE) S.scriptNiche = 0;
      render();
      loadScripts().then(function () { if (S.tab === "scripts") render(true); }).catch(function (error) { toast(error.message); });
    } else {
      render();
    }
  } else if (action === "niche") {
    S.niche = Number(value);
    render(true);
  } else if (action === "flt") {
    S.flt = value;
    render(true);
  } else if (action === "count") {
    S.count = Number(value);
    render(true);
  } else if (action === "filter") {
    S.filter = value;
    render(true);
  } else if (action === "go") {
    go();
  } else if (action === "demand") {
    showDemand();
  } else if (action === "pickniche") {
    S.niche = Number(value);
    closeSheet();
    S.tab = "search";
    render();
    toast("Ниша выбрана: " + nicheTitle(S.niche) + ".");
  } else if (action === "close") {
    closeSheet();
  } else if (action === "offer") {
    showTrialOffer(S.trialOffer || { message: S.access && S.access.trial_message });
  } else if (action === "status") {
    var lead = findLead(id);
    if (lead) saveLeadStatus(lead, lead.status === value ? "new" : value);
  } else if (action === "phones") {
    S.open[id] = !S.open[id];
    render(true);
  } else if (action === "leadscript" || action === "leadkind") {
    var scriptLead = findLead(id);
    if (scriptLead) generateLeadScript(scriptLead, action === "leadkind" ? value : "first", 0);
  } else if (action === "leadmore") {
    var moreLead = findLead(S.genLead);
    if (moreLead) generateLeadScript(moreLead, value, (S.genVariant || 0) + 1);
  } else if (action === "nichemore") {
    generateNicheScript(value, (S.genVariant || 1) + 1);
  } else if (action === "copygen") {
    copyText(S.sheetText || "");
  } else if (action === "savegen") {
    saveGenerated(value);
  } else if (action === "export") {
    api("/api/export", { method: "POST" }).then(function (data) {
      toast(data.message || "Excel-файл придёт в чат с ботом.");
    }).catch(function (error) { toast(error.message); });
  } else if (action === "sopen") {
    S.scriptOpen[id] = !S.scriptOpen[id];
    render(true);
  } else if (action === "scopy") {
    var script = S.scripts.filter(function (item) { return String(item.id) === id; })[0];
    if (script) copyText(script.body);
  } else if (action === "sedit") {
    S.scriptEdit = Number(id);
    render(true);
  } else if (action === "scancel") {
    S.scriptEdit = null;
    render(true);
  } else if (action === "sdel") {
    api("/api/scripts/" + encodeURIComponent(id), { method: "DELETE" }).then(function () {
      return loadScripts();
    }).then(function () { render(true); toast("Скрипт удалён."); }).catch(function (error) { toast(error.message); });
  } else if (action === "genniche") {
    generateNicheScript(value, 1);
  } else if (action === "atab") {
    S.atab = value;
    S.newKey = "";
    render(true);
    loadAdmin().then(function () { render(true); }).catch(function (error) { toast(error.message); });
  } else if (action === "edit") {
    var user = S.users.filter(function (item) { return String(item.id) === id; })[0];
    if (!user) return;
    S.editId = S.editId === user.id ? null : user.id;
    S.editVal = user.lim;
    render(true);
  } else if (action === "limd") {
    S.editVal = Math.max(0, Math.min(5000, S.editVal + Number(value)));
    render(true);
  } else if (action === "limset") {
    S.editVal = Number(value);
    render(true);
  } else if (action === "limcancel") {
    S.editId = null;
    render(true);
  } else if (action === "limsave") {
    var editId = S.editId;
    S.editId = null;
    adminAction("/api/admin/users/" + encodeURIComponent(editId) + "/limit", { limit: S.editVal }, "Лимит обновлён.");
  } else if (action === "access") {
    adminAction("/api/admin/users/" + encodeURIComponent(id) + "/access", { approved: value === "1" },
      value === "1" ? "Полный доступ выдан." : "Полный доступ закрыт.");
  } else if (action === "bonus") {
    adminAction("/api/admin/users/" + encodeURIComponent(id) + "/bonus", { amount: Number(value) }, "Запросы добавлены.");
  } else if (action === "ban") {
    adminAction("/api/admin/users/" + encodeURIComponent(id) + "/ban", { banned: value === "1" },
      value === "1" ? "Пользователь заблокирован." : "Пользователь разблокирован.");
  } else if (action === "copykey" || action === "copyval") {
    copyText(value);
  } else if (action === "delkey") {
    api("/api/admin/keys/" + encodeURIComponent(value), { method: "DELETE" }).then(function () {
      return loadAdmin();
    }).then(function () { render(true); toast("Ключ удалён."); }).catch(function (error) { toast(error.message); });
  } else if (action === "blocklead") {
    adminAction("/api/admin/blocked", { lead_id: Number(id) }, "Бизнес добавлен в чёрный список.");
  } else if (action === "unblock") {
    adminAction("/api/admin/unblock", { label: value }, "Убрано из чёрного списка.");
  } else if (action === "tip") {
    var wasOpen = button.classList.contains("open");
    document.querySelectorAll(".hot.open").forEach(function (node) { node.classList.remove("open"); });
    if (!wasOpen) button.classList.add("open");
  } else if (action === "refresh") {
    refreshAll().then(function () { toast("Данные обновлены."); }).catch(function (error) { toast(error.message); });
  }
}

document.addEventListener("click", clickHandler);
document.addEventListener("input", function (event) {
  if (event.target.id === "city") S.city = event.target.value;
  if (event.target.id === "cn") S.custom = event.target.value;
  if (event.target.id === "user-q") {
    S.userQuery = event.target.value;
    var position = event.target.selectionStart;
    render(true);
    var input = $("#user-q");
    if (input) { input.focus(); try { input.setSelectionRange(position, position); } catch (_) {} }
  }
});
document.addEventListener("change", function (event) {
  if (event.target.id === "country") {
    S.country = event.target.value;
    render(true);
  }
  if (event.target.id === "sniche") {
    S.scriptNiche = Number(event.target.value);
    S.scripts = [];
    S.scriptEdit = null;
    S.scriptOpen = {};
    render(true);
    loadScripts().then(function () { if (S.tab === "scripts") render(true); }).catch(function (error) { toast(error.message); });
  }
});
document.addEventListener("toggle", function (event) {
  if (event.target.dataset && event.target.dataset.intro === "scripts") S.scrIntro = event.target.open;
}, true);
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape" && $("#sheet").classList.contains("show")) closeSheet();
});

function formValue(form, name) {
  return String(new FormData(form).get(name) || "").trim();
}

document.addEventListener("submit", function (event) {
  var form = event.target;
  var id = form.id;
  if (!id) return;
  event.preventDefault();
  if (id === "key-form") {
    var code = formValue(form, "code").toUpperCase();
    if (code.length < 4) { toast("Введите ключ доступа."); return; }
    api("/api/key", { method: "POST", body: JSON.stringify({ code: code }) }).then(function (result) {
      closeSheet();
      return loadMe().then(function () { render(); toast(result.message || "Ключ активирован."); });
    }).catch(function (error) { toast(error.message); });
  } else if (id === "script-form") {
    var payload = {
      niche: S.scriptNiche, kind: form.dataset.kind || "first",
      title: formValue(form, "title"), body: formValue(form, "body")
    };
    if (!payload.title || !payload.body) { toast("Заполните название и текст."); return; }
    api("/api/scripts/" + encodeURIComponent(form.dataset.id), { method: "PUT", body: JSON.stringify(payload) }).then(function (result) {
      S.scriptEdit = null;
      return loadScripts().then(function () {
        render(true);
        toast(result.copy ? "Сохранено как ваш скрипт." : "Скрипт сохранён.");
      });
    }).catch(function (error) { toast(error.message); });
  } else if (id === "grant-form") {
    var limit = formValue(form, "limit");
    adminAction("/api/admin/grant", { query: formValue(form, "query"), limit: limit ? Number(limit) : null }, "Доступ выдан.");
  } else if (id === "key-create") {
    api("/api/admin/keys", {
      method: "POST",
      body: JSON.stringify({
        for_user: formValue(form, "for_user"), limit: Number(formValue(form, "limit") || 0),
        bonus: Number(formValue(form, "bonus") || 0), uses: Number(formValue(form, "uses") || 1), note: formValue(form, "note")
      })
    }).then(function (result) {
      S.newKey = result.code;
      return loadAdmin().then(function () { render(true); toast("Ключ создан."); });
    }).catch(function (error) { toast(error.message); });
  } else if (id === "aleads-form") {
    S.adminQuery = formValue(form, "q");
    loadAdmin().then(function () { render(true); }).catch(function (error) { toast(error.message); });
  } else if (id === "block-form") {
    adminAction("/api/admin/blocked", { text: formValue(form, "text") }, "Добавлено в чёрный список.");
  } else if (id === "broadcast-form") {
    var text = formValue(form, "text");
    if (!text) { toast("Введите текст рассылки."); return; }
    api("/api/admin/broadcast", { method: "POST", body: JSON.stringify({ text: text }) }).then(function (result) {
      form.reset();
      toast(result.message || "Рассылка запущена.");
    }).catch(function (error) { toast(error.message); });
  }
});

function appReady() {
  if (typeof window.__appReady === "function") window.__appReady();
}

function boot() {
  if (tg) {
    try { tg.ready(); tg.expand(); } catch (_) {}
    if (tg.colorScheme === "light") setTheme("light");
  }
  refreshAll().then(appReady).catch(function (error) {
    appReady();
    var app = $("#app");
    var banned = error.detail && error.detail.code === "banned";
    app.innerHTML = '<section class="screen"><div class="card"><h2>' + (banned ? "Доступ закрыт" : "Не удалось открыть приложение") + "</h2>" +
      '<p class="muted">' + esc(error.message) + '</p><p class="muted small">' +
      (banned ? "" : error.status === 401
        ? "Откройте Mini App через бота в Telegram. Если окно было открыто долго, закройте его и откройте снова."
        : "Проверьте соединение и снова откройте приложение.") +
      "</p>" + (banned ? "" : '<button class="ghost" data-act="refresh">Повторить</button>') + "</div></section>";
    $("#tabs").innerHTML = "";
  });
}

setTheme("dark");
render();
boot();
