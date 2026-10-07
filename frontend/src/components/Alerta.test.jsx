import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Alerta from './Alerta';

describe('Alerta', () => {
  it('erro usa role=alert', () => {
    render(<Alerta>Falhou</Alerta>);
    expect(screen.getByRole('alert')).toHaveTextContent('Falhou');
  });

  it('sucesso usa role=status', () => {
    render(<Alerta tipo="sucesso">Salvo</Alerta>);
    expect(screen.getByRole('status')).toHaveTextContent('Salvo');
  });

  it('não renderiza nada sem conteúdo', () => {
    const { container } = render(<Alerta>{null}</Alerta>);
    expect(container).toBeEmptyDOMElement();
  });
});
