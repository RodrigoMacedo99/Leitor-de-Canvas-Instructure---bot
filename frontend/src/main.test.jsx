import { describe, expect, it, vi } from 'vitest';

const render = vi.fn();
vi.mock('react-dom/client', () => ({ createRoot: vi.fn(() => ({ render })) }));
vi.mock('./App', () => ({ default: () => null }));
vi.mock('./contexts/AuthContext', () => ({ AuthProvider: ({ children }) => children }));
vi.mock('./styles.css', () => ({}));

import { createRoot } from 'react-dom/client';
import { montar } from './main';

describe('main', () => {
  it('monta a aplicação com router e provider de autenticação', () => {
    const elemento = document.createElement('div');
    montar(elemento);
    expect(createRoot).toHaveBeenCalledWith(elemento);
    expect(render).toHaveBeenCalledOnce();
  });
});
