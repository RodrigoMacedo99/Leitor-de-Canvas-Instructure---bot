const { readConfig } = require('../../../src/integrations/canvas/config');

describe('readConfig', () => {
  it('lê URL e token do ambiente e usa a pasta padrão', () => {
    const config = readConfig({
      CANVAS_BASE_URL: 'https://x.instructure.com/',
      CANVAS_TOKEN: 'tok',
    });

    expect(config).toEqual({
      baseUrl: 'https://x.instructure.com',
      token: 'tok',
      outputDir: 'canvas-data',
    });
  });

  it('respeita CANVAS_OUTPUT_DIR quando definida', () => {
    const config = readConfig({
      CANVAS_BASE_URL: 'https://x.instructure.com',
      CANVAS_TOKEN: 'tok',
      CANVAS_OUTPUT_DIR: '/dados/canvas',
    });

    expect(config.outputDir).toBe('/dados/canvas');
  });

  it('falha de forma explícita quando falta o token', () => {
    expect(() => readConfig({ CANVAS_BASE_URL: 'https://x.instructure.com' })).toThrow(
      /CANVAS_BASE_URL e CANVAS_TOKEN/
    );
  });

  it('rejeita uma URL que não é válida', () => {
    expect(() => readConfig({ CANVAS_BASE_URL: 'não-é-url', CANVAS_TOKEN: 'tok' })).toThrow(
      /CANVAS_BASE_URL inválida/
    );
  });
});
