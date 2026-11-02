import http from 'k6/http';
import { check, sleep } from 'k6';

const baseUrl = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const routes = ['/', '/organizaciones/', '/iniciar-sesion/', '/health/'];
let loggedFailures = 0;

export const options = {
  discardResponseBodies: false,
  vus: 5,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

export default function () {
  const route = routes[(__ITER + __VU) % routes.length];
  const response = http.get(`${baseUrl}${route}`, { redirects: 3, timeout: '15s' });
  const ok = response.status >= 200 && response.status < 400;

  if (!ok && loggedFailures < 20) {
    console.log(`FAIL route=${route} status=${response.status} error=${response.error || 'none'} body=${String(response.body).slice(0, 160)}`);
    loggedFailures += 1;
  }

  check(response, { [`${route} responde 2xx/3xx`]: () => ok });
  sleep(1);
}
