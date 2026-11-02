import http from 'k6/http';
import { check, sleep } from 'k6';

const baseUrl = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const profile = __ENV.LOAD_PROFILE || 'smoke';
const isProduction = /^https?:\/\/tradicionviva\.com\.gt(?:\/|$)/i.test(baseUrl);

if (profile === 'stress' && isProduction && __ENV.ALLOW_PRODUCTION_LOAD !== 'true') {
  throw new Error(
    'El perfil stress está bloqueado contra producción. Usa un entorno de pruebas o confirma explícitamente con ALLOW_PRODUCTION_LOAD=true.',
  );
}

const profiles = {
  smoke: [
    { duration: '30s', target: 5 },
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  step1: [
    { duration: '30s', target: 100 },
    { duration: '1m', target: 500 },
    { duration: '1m', target: 1000 },
    { duration: '30s', target: 0 },
  ],
  step2: [
    { duration: '20s', target: 50 },
    { duration: '30s', target: 100 },
    { duration: '30s', target: 150 },
    { duration: '30s', target: 200 },
    { duration: '30s', target: 0 },
  ],
  staged: [
    { duration: '1m', target: 100 },
    { duration: '2m', target: 1000 },
    { duration: '2m', target: 5000 },
    { duration: '2m', target: 10000 },
    { duration: '1m', target: 0 },
  ],
  stress: [
    { duration: '2m', target: 1000 },
    { duration: '3m', target: 5000 },
    { duration: '3m', target: 10000 },
    { duration: '3m', target: 25000 },
    { duration: '2m', target: 30000 },
    { duration: '2m', target: 0 },
  ],
};

export const options = {
  discardResponseBodies: true,
  stages: profiles[profile] || profiles.smoke,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1500', 'p(99)<3000'],
    checks: ['rate>0.99'],
  },
};

const publicRoutes = [
  '/',
  '/organizaciones/',
  '/iniciar-sesion/',
  '/health/',
];

export default function () {
  const route = publicRoutes[(__ITER + __VU) % publicRoutes.length];
  const response = http.get(`${baseUrl}${route}`, {
    tags: { route },
    redirects: 3,
    timeout: '15s',
  });

  check(response, {
    [`${route} responde 2xx/3xx`]: (res) => res.status >= 200 && res.status < 400,
  });

  sleep(1);
}
