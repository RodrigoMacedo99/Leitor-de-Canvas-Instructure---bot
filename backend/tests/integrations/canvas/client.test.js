const { createCanvasClient, CanvasApiError } = require('../../../src/integrations/canvas/client');

const BASE = 'https://x.instructure.com';

function jsonResponse(body, { status = 200, link } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: name => (name.toLowerCase() === 'link' ? link || null : null) },
    json: () => Promise.resolve(body),
  };
}

describe('createCanvasClient', () => {
  it('envia o token como Bearer e monta a URL da API v1', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(jsonResponse([]));
    const client = createCanvasClient({ baseUrl: BASE, token: 'tok', fetchImpl });

    await client.getAll('/courses');

    const [url, options] = fetchImpl.mock.calls[0];
    expect(url).toBe(`${BASE}/api/v1/courses?per_page=100`);
    expect(options.headers.Authorization).toBe('Bearer tok');
  });

  it('serializa arrays como chave[] (formato do Canvas)', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(jsonResponse([]));
    const client = createCanvasClient({ baseUrl: BASE, token: 'tok', fetchImpl });

    await client.getAll('/courses/1/modules', { include: ['items', 'content_details'] });

    const url = new URL(fetchImpl.mock.calls[0][0]);
    expect(url.searchParams.getAll('include[]')).toEqual(['items', 'content_details']);
  });

  it('segue o header Link e junta todas as páginas', async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValueOnce(
        jsonResponse([{ id: 1 }], { link: `<${BASE}/api/v1/courses?page=2>; rel="next"` })
      )
      .mockResolvedValueOnce(jsonResponse([{ id: 2 }]));
    const client = createCanvasClient({ baseUrl: BASE, token: 'tok', fetchImpl });

    const items = await client.getAll('/courses');

    expect(items).toEqual([{ id: 1 }, { id: 2 }]);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(fetchImpl.mock.calls[1][0]).toBe(`${BASE}/api/v1/courses?page=2`);
  });

  it('repete em 429 com backoff exponencial e depois tem sucesso', async () => {
    const sleep = jest.fn().mockResolvedValue();
    const fetchImpl = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse({}, { status: 429 }))
      .mockResolvedValueOnce(jsonResponse({}, { status: 503 }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const client = createCanvasClient({ baseUrl: BASE, token: 'tok', fetchImpl, sleep });

    const data = await client.getJson('/courses/1');

    expect(data).toEqual({ ok: true });
    expect(sleep.mock.calls.map(c => c[0])).toEqual([1000, 2000]);
  });

  it('desiste após esgotar as tentativas e lança CanvasApiError', async () => {
    const sleep = jest.fn().mockResolvedValue();
    const fetchImpl = jest.fn().mockResolvedValue(jsonResponse({}, { status: 500 }));
    const client = createCanvasClient({ baseUrl: BASE, token: 'tok', fetchImpl, sleep });

    await expect(client.getJson('/courses/1')).rejects.toMatchObject({
      name: 'CanvasApiError',
      status: 500,
    });
    expect(fetchImpl).toHaveBeenCalledTimes(4);
  });

  it('não repete erros de cliente como 401 e expõe o status', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(jsonResponse({}, { status: 401 }));
    const client = createCanvasClient({ baseUrl: BASE, token: 'tok', fetchImpl });

    const error = await client.getJson('/courses').catch(e => e);

    expect(error).toBeInstanceOf(CanvasApiError);
    expect(error.status).toBe(401);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
