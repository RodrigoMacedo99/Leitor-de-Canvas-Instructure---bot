const { safeSegment, courseDirName } = require('../../../src/integrations/canvas/paths');

describe('safeSegment', () => {
  it('mantém nomes simples e acentuados', () => {
    expect(safeSegment('Cálculo I - Turma A')).toBe('Cálculo I - Turma A');
  });

  it('substitui separadores de caminho e caracteres reservados', () => {
    expect(safeSegment('a/b\\c:d*e?')).toBe('a_b_c_d_e_');
  });

  it('impede traversal com ".." ou nomes ocultos', () => {
    expect(safeSegment('../../etc/passwd')).toBe('_.._etc_passwd');
    expect(safeSegment('.bashrc')).toBe('bashrc');
  });

  it('usa o fallback quando sobra nada utilizável', () => {
    expect(safeSegment('...')).toBe('sem-nome');
    expect(safeSegment(undefined)).toBe('sem-nome');
  });

  it('limita o tamanho do segmento', () => {
    expect(safeSegment('x'.repeat(500))).toHaveLength(120);
  });
});

describe('courseDirName', () => {
  it('combina id e nome do curso para manter a pasta única e legível', () => {
    expect(courseDirName({ id: 42, name: 'Física II' })).toBe('42-Física II');
  });
});
