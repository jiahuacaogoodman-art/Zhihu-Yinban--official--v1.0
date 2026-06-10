/* 智护银伴 Service Worker · 新版 SPA 专用 */
const CACHE_NAME = 'zhihu-spa-only-v25';
const STATIC_ASSETS = [
  '/',
  '/nurse',
  '/static/manifest.json',
  '/static/design/tokens.css',
  '/static/design/glass.css',
  '/static/design/ui.css',
  '/static/design/mobile.css',
  '/static/design/ambient.svg',
  '/static/design/select-chevron.svg',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

const NETWORK_FIRST_PATHS = [
  '/v2/assets/',
  '/static/dist/assets/',
  '/static/design/',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      cache.addAll(STATIC_ASSETS).catch(() => {})
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  if (event.request.method !== 'GET') {
    return;
  }

  // API 请求：网络优先，离线返回提示
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(
          JSON.stringify({ code: 503, message: '当前处于离线状态，无法请求 AI 服务' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    );
    return;
  }

  // 外部资源（字体等）：网络优先，失败从缓存
  if (url.origin !== self.location.origin) {
    event.respondWith(
      fetch(event.request)
        .then(res => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // 页面请求：网络优先；离线时回到对应 SPA 壳。
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() =>
        caches.match(url.pathname.startsWith('/nurse') ? '/nurse' : '/')
      )
    );
    return;
  }

  // 构建产物和设计系统 CSS 必须网络优先，避免浏览器继续显示旧版错位样式。
  if (NETWORK_FIRST_PATHS.some(path => url.pathname.startsWith(path))) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache =>
        fetch(event.request)
          .then(res => {
            if (res && res.status === 200) cache.put(event.request, res.clone());
            return res;
          })
          .catch(() => cache.match(event.request))
      )
    );
    return;
  }

  // 静态资源：Stale-While-Revalidate
  event.respondWith(
    caches.open(CACHE_NAME).then(cache =>
      cache.match(event.request).then(cached => {
        const fetchPromise = fetch(event.request).then(res => {
          if (res && res.status === 200) cache.put(event.request, res.clone());
          return res;
        }).catch(() => null);
        return cached || fetchPromise;
      })
    )
  );
});