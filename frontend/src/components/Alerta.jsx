/** Mensagem de erro/aviso/sucesso acessível (role="alert" só para erro). */
export default function Alerta({ tipo = 'erro', children }) {
  if (!children) return null;
  return (
    <p
      className={`alerta alerta-${tipo}`}
      role={tipo === 'erro' ? 'alert' : 'status'}
      data-testid={`alerta-${tipo}`}
    >
      {children}
    </p>
  );
}
