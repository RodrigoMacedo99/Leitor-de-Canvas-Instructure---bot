const { parseNextLink } = require('../../../src/integrations/canvas/pagination');

describe('parseNextLink', () => {
  it('retorna a URL do rel="next" quando existe', () => {
    const header =
      '<https://x.instructure.com/api/v1/courses?page=1>; rel="current",' +
      '<https://x.instructure.com/api/v1/courses?page=2>; rel="next",' +
      '<https://x.instructure.com/api/v1/courses?page=9>; rel="last"';

    expect(parseNextLink(header)).toBe('https://x.instructure.com/api/v1/courses?page=2');
  });

  it('retorna null na última página', () => {
    const header = '<https://x.instructure.com/api/v1/courses?page=3>; rel="current"';

    expect(parseNextLink(header)).toBeNull();
  });

  it('retorna null quando não há header Link', () => {
    expect(parseNextLink(null)).toBeNull();
  });
});
