import type { LegalSection } from '@/components/legal-document';

export const PRIVACY_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Quiénes somos y alcance',
    paragraphs: [
      'Fincilia es una plataforma de conciliación y control financiero desarrollada por Parallext.com. El entorno de preproducción actual opera exclusivamente con datos inventados y no admite documentos financieros reales.',
      'La entidad jurídica que actuará como responsable o encargado, su domicilio y los canales formales se completarán con revisión legal antes de habilitar datos reales. El contacto provisional de privacidad es support@parallext.com.',
    ],
  },
  {
    title: 'Datos que tratamos',
    bullets: [
      'Datos de cuenta: nombre visible, correo o identificador del proveedor de identidad y estado de la cuenta.',
      'Datos de seguridad y operación: roles, sesiones, eventos de auditoría, dirección IP en la capa de infraestructura y diagnóstico técnico limitado.',
      'Datos de uso: acciones realizadas, errores, tiempos y métricas necesarias para seguridad y mejora del servicio.',
      'Mientras los gates de datos permanezcan cerrados, empresas, cuentas, documentos, movimientos y referencias deben ser completamente sintéticos.',
    ],
  },
  {
    title: 'Inicio de sesión con Google',
    paragraphs: [
      'Cuando se habilite, Google se usará únicamente para autenticar y crear el perfil básico de Fincilia. Se solicitarán los scopes openid, email y profile para obtener un identificador estable, correo verificado y nombre visible.',
      'Fincilia no solicitará acceso a Gmail, Google Drive, contactos o calendario; no venderá esos datos, no los usará para publicidad y no los enviará a modelos de IA. La integración permanecerá apagada mientras el gate de datos personales esté cerrado.',
    ],
  },
  {
    title: 'Finalidades y bases candidatas',
    bullets: [
      'Crear y proteger la cuenta, resolver roles y prestar las funciones solicitadas.',
      'Prevenir abuso, investigar incidentes, conservar auditoría y cumplir obligaciones aplicables.',
      'Medir estabilidad y mejorar la experiencia del servicio con información minimizada.',
      'Las bases jurídicas definitivas —ejecución contractual, obligación legal, interés legítimo o consentimiento— se documentarán por actividad antes de datos reales.',
    ],
  },
  {
    title: 'Conservación, transferencias y proveedores',
    paragraphs: [
      'El entorno de preproducción conserva cuentas y evidencia sintética mientras dure la prueba o hasta una solicitud de eliminación. Registros de seguridad y copias pueden permanecer durante una ventana limitada para investigación y restauración.',
      'La infraestructura evaluada está en AWS São Paulo. Google solo participará como proveedor de identidad cuando sea habilitado. La decisión de transmisión internacional, el DPA y la lista definitiva de subencargados siguen pendientes antes de datos reales.',
    ],
  },
  {
    title: 'Tus opciones y derechos',
    paragraphs: [
      'Puedes pedir acceso, corrección, eliminación, restricción o información sobre tu cuenta escribiendo a support@parallext.com. Verificaremos la identidad antes de actuar y explicaremos cualquier conservación obligatoria o bloqueo técnico.',
      'Fincilia no está dirigida a menores de edad. Si detectamos una cuenta de un menor, la suspenderemos y coordinaremos su eliminación.',
    ],
  },
];

export const TERMS_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Naturaleza del entorno actual',
    paragraphs: [
      'Fincilia se encuentra en preproducción mientras completa controles, revisiones y despliegue. No constituye un servicio contable certificado, una auditoría, asesoría financiera ni una promesa de disponibilidad.',
      'El registro puede ser público mediante Google, pero los datos operativos deben seguir siendo inventados hasta que Fincilia comunique expresamente la habilitación de datos reales. No cargues extractos, facturas, NIT, cuentas o movimientos reales mientras esa restricción aparezca en el servicio.',
    ],
  },
  {
    title: 'Cuenta y responsabilidades',
    bullets: [
      'Mantén tus credenciales bajo control y reporta accesos no reconocidos.',
      'Usa roles distintos para probar funciones, sin suplantar personas reales.',
      'No intentes evadir aislamiento, límites, auditoría o controles de seguridad.',
      'Reporta fallos de forma privada; no publiques datos o detalles explotables.',
    ],
  },
  {
    title: 'Usos prohibidos',
    bullets: [
      'Datos personales, financieros, bancarios, tributarios o confidenciales reales.',
      'Fraude, malware, scraping abusivo, pruebas de carga no acordadas o acceso no autorizado.',
      'Decisiones contables o legales reales basadas en resultados del entorno de preproducción.',
      'Reventa, sublicencia o representación de Fincilia como servicio propio.',
    ],
  },
  {
    title: 'Propiedad y comentarios',
    paragraphs: [
      'Fincilia, su software, marca y diseño pertenecen a sus titulares. Parallext.com desarrolla el producto. Conservas los derechos sobre material que estés autorizado a usar; mientras los gates de datos estén cerrados ese material debe ser sintético.',
      'Los comentarios de producto pueden usarse para mejorar Fincilia sin revelar tu identidad. No envíes secretos, datos reales o propiedad de terceros dentro del feedback.',
    ],
  },
  {
    title: 'Disponibilidad, suspensión y cambios',
    paragraphs: [
      'Podemos modificar, detener o reiniciar el entorno de preproducción para corregir fallos o protegerlo. Podemos suspender cuentas ante abuso o riesgo. Cuando sea razonable avisaremos cambios materiales por los canales de soporte publicados.',
      'La ley aplicable, jurisdicción, limitaciones de responsabilidad y datos corporativos definitivos deben ser aprobados por Legal antes de convertir estos términos en condiciones productivas.',
    ],
  },
];

export const COOKIE_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Qué usamos hoy',
    bullets: [
      'fincilia_session: cookie httpOnly y SameSite que mantiene una sesión corta.',
      'fincilia_session_name: nombre visible usado para la interfaz; no contiene permisos ni decide acceso.',
      'Cookies transitorias OAuth: state, nonce y verificador PKCE cuando Google sea habilitado; se eliminan al terminar o vencer el intento.',
    ],
  },
  {
    title: 'Qué no usamos',
    paragraphs: [
      'Fincilia no instala cookies publicitarias, de seguimiento entre sitios ni analítica de terceros. Si se propone analítica opcional, se documentará el proveedor, finalidad y duración y se pedirá consentimiento antes de activarla cuando corresponda.',
    ],
  },
  {
    title: 'Control y duración',
    paragraphs: [
      'Puedes borrar cookies desde el navegador. Hacerlo cierra la sesión o interrumpe un ingreso en curso. Las cookies de sesión duran como máximo lo que dura el token y las transitorias OAuth unos minutos.',
    ],
  },
];

export const SECURITY_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Controles actuales',
    bullets: [
      'Aislamiento por empresa con PostgreSQL RLS forzada y autorización resuelta en servidor.',
      'Dinero decimal exacto, auditoría append-only y linaje de hechos financieros.',
      'Cookies httpOnly, sesiones cortas, rate limiting y secretos fuera del repositorio.',
      'Imágenes fijadas por digest, migraciones separadas y administración cloud mediante SSM sin SSH.',
    ],
  },
  {
    title: 'Límites de preproducción',
    paragraphs: [
      'El entorno actual no está autorizado para datos reales y todavía no se presenta como infraestructura de producción. Pentest independiente, restore con tombstones, DPA, evaluación PCI cuando aplique y revisiones nominales siguen siendo condiciones para DRG-01.',
    ],
  },
  {
    title: 'Reporte responsable',
    paragraphs: [
      'Envía hallazgos de forma privada a support@parallext.com con una descripción, impacto y pasos mínimos de reproducción. No incluyas secretos ni datos de terceros. Confirmaremos recepción y coordinaremos la divulgación responsable.',
    ],
  },
];

export const DPA_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Estado de este documento',
    paragraphs: [
      'Esta página resume la plantilla de acuerdo de tratamiento prevista para Fincilia. No constituye un DPA firmado ni autoriza a enviar datos reales. Cada participante deberá acordar partes, roles, finalidad, instrucciones y anexos antes de DRG-00 o DRG-01 según el flujo.',
    ],
  },
  {
    title: 'Contenido previsto',
    bullets: [
      'Objeto, duración, naturaleza, finalidad y categorías de datos y titulares.',
      'Confidencialidad, seguridad, subencargados y transferencias internacionales.',
      'Asistencia con derechos, incidentes, evaluaciones, auditorías y autoridad competente.',
      'Retorno, eliminación, legal hold, backups y evidencia de cumplimiento.',
      'Anexos de medidas técnicas, región, contacto, SLA y matriz de retención.',
    ],
  },
  {
    title: 'Cómo solicitarlo',
    paragraphs: [
      'Escribe a support@parallext.com indicando la organización, país y caso de uso. Legal debe responder con la entidad contratante y versión aplicable; la aceptación de términos web no firma automáticamente este DPA.',
    ],
  },
];

export const SUBPROCESSOR_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Proveedores previstos',
    bullets: [
      'Amazon Web Services: cómputo, almacenamiento, red, secretos, logs e identidad administrada; región inicial evaluada sa-east-1 (São Paulo).',
      'Google: autenticación social opcional con openid, email y profile; deshabilitada mientras DRG-00 esté cerrado.',
      'Parallext.com: desarrollo, operación y soporte del producto bajo acceso mínimo y auditado.',
    ],
  },
  {
    title: 'Cambios y objeciones',
    paragraphs: [
      'La lista productiva, ubicaciones y mecanismos de transferencia deben cerrarse mediante A-02/L-02 y DPA. Antes de añadir un proveedor que reciba datos reales se hará due diligence y se definirá un mecanismo de notificación y objeción.',
    ],
  },
];

export const DELETION_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Solicitar eliminación',
    paragraphs: [
      'Escribe desde el correo asociado a support@parallext.com con el asunto “Eliminar cuenta Fincilia”. No incluyas contraseñas, documentos o información financiera. Podemos pedir una verificación adicional para impedir que otra persona elimine tu cuenta.',
    ],
  },
  {
    title: 'Qué ocurre después',
    bullets: [
      'Se bloquea el acceso y se elabora un inventario de la cuenta, las membresías, los objetos, las exportaciones y los eventos relacionados antes de ejecutar la eliminación.',
      'Se aplican tombstones antes de purgar copias activas y se reaplican al restaurar backups.',
      'Se informa lo eliminado, lo retenido por seguridad u obligación aplicable y la fecha estimada de reconciliación.',
      'En preproducción sintética podemos eliminar el espacio completo; la operación con datos reales aplicará reglas por clase y legal hold.',
    ],
  },
  {
    title: 'Google',
    paragraphs: [
      'Eliminar Fincilia no elimina tu cuenta Google. También puedes retirar el acceso desde la configuración de tu cuenta Google cuando la integración esté habilitada. Fincilia dejará de usar el vínculo y conservará solo lo exigido por seguridad o ley.',
    ],
  },
];
