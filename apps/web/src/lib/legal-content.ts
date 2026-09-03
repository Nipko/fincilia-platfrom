import type { LegalSection } from '@/components/legal-document';

const CONTROLLER = 'Parallext LLC';
const ADDRESS = '7345 W Sand Lake Rd, Ste 210, Office 2812, Orlando, Florida 32819, Estados Unidos';
const PHONE = '+57 313 432 8491';

export const PRIVACY_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Responsable y alcance',
    paragraphs: [
      `Fincilia es un producto operado por ${CONTROLLER} y desarrollado bajo la marca Parallext.com. Para los datos de cuenta, seguridad, facturación, soporte y uso del sitio, ${CONTROLLER} actúa como responsable del tratamiento. Domicilio de contacto: ${ADDRESS}. Teléfono: ${PHONE}.`,
      'Cuando una organización usa Fincilia para procesar documentos o información financiera bajo sus propias instrucciones, esa organización determina las finalidades empresariales y Parallext LLC actúa como encargado o proveedor de servicios conforme al contrato y, cuando corresponda, al acuerdo de tratamiento de datos (DPA).',
      'Puedes escribir a privacy@fincilia.com para asuntos de datos personales, a legal@fincilia.com para asuntos contractuales y a support@fincilia.com para soporte general.',
    ],
  },
  {
    title: 'Información que tratamos',
    bullets: [
      'Identidad y cuenta: identificador del proveedor, nombre visible, correo verificado, estado de cuenta, organización, membresías y roles. Fincilia no recibe ni almacena tu contraseña de Google.',
      'Seguridad y operación: sesiones, eventos de acceso y auditoría, dirección IP y metadatos técnicos limitados, intentos fallidos, diagnósticos y señales necesarias para prevenir abuso.',
      'Servicio: configuración de empresas, fuentes, documentos, columnas, movimientos, conciliaciones, observaciones y evidencia que una organización decida cargar cuando el entorno correspondiente esté autorizado.',
      'Soporte y comunicaciones: solicitudes, preferencias de notificación, mensajes operativos y la información que decidas incluir al contactar nuestros canales.',
      'Facturación: plan, consumo, país de facturación y referencias de pago cuando se active un proveedor de cobro. Fincilia no almacenará números completos de tarjeta ni códigos de seguridad.',
      'Sitio web: cookies estrictamente necesarias y datos técnicos mínimos descritos en el aviso de cookies. No usamos publicidad comportamental ni seguimiento entre sitios.',
    ],
  },
  {
    title: 'Finalidades y autorización',
    bullets: [
      'Crear y administrar la cuenta, autenticarte, resolver permisos y prestar las funciones solicitadas.',
      'Procesar información empresarial siguiendo las instrucciones documentadas de la organización que controla esos datos.',
      'Proteger la plataforma, detectar abuso, investigar incidentes, conservar trazabilidad y cumplir obligaciones legales.',
      'Atender soporte, consultas, reclamos, solicitudes de privacidad y comunicaciones operativas.',
      'Gestionar planes, consumo, pagos e impuestos cuando la facturación esté habilitada.',
      'Medir estabilidad y mejorar el servicio mediante métricas minimizadas. No usamos documentos financieros para entrenar modelos de inteligencia artificial sin una autorización y un acuerdo separados.',
    ],
    paragraphs: [
      'Solicitamos autorización previa e informada cuando la ley la exige y conservamos evidencia de la versión aceptada. También podemos tratar información cuando sea necesario para prestar el servicio solicitado, proteger la plataforma o cumplir una obligación aplicable, siempre dentro de los límites legales. Las comunicaciones comerciales opcionales requerirán una elección separada.',
    ],
  },
  {
    title: 'Inicio de sesión con Google',
    paragraphs: [
      'Si eliges continuar con Google, solicitamos únicamente openid, email y profile. Google entrega un identificador estable, correo verificado y nombre visible para autenticarte y crear o localizar tu perfil de Fincilia. No solicitamos acceso a Gmail, Google Drive, contactos, calendario ni archivos de tu cuenta Google.',
      'Usamos esos datos solo para identidad, seguridad, creación de cuenta y soporte asociado. No los vendemos, no los usamos para publicidad, no los enviamos a modelos de inteligencia artificial y no los compartimos salvo con los proveedores necesarios para operar la autenticación y el servicio.',
      'El uso y transferencia de información recibida de las API de Google se limita a las finalidades aquí descritas y observa la Política de Datos de Usuario de los Servicios de API de Google, incluidos sus requisitos de uso limitado.',
    ],
  },
  {
    title: 'Destinatarios, proveedores y transferencias',
    paragraphs: [
      'Podemos comunicar información a la organización a la que perteneces, a sus administradores autorizados, a proveedores contratados que actúan bajo instrucciones y a autoridades cuando una obligación válida lo requiera. No vendemos datos personales.',
      'La infraestructura principal evaluada para Fincilia está en Amazon Web Services, región São Paulo, Brasil. Google participa en la autenticación; Namecheap Private Email presta los buzones de contacto; Cloudflare administra DNS y puede prestar controles de red cuando se habiliten. La lista vigente y las finalidades se publican en /subencargados.',
      'Cuando el tratamiento implique una transmisión o transferencia internacional, aplicaremos el contrato, las instrucciones, medidas de seguridad y mecanismos exigidos por la ley aplicable. Una organización empresarial puede solicitar el DPA antes de habilitar datos propios.',
    ],
  },
  {
    title: 'Conservación y eliminación',
    paragraphs: [
      'Conservamos cada categoría únicamente mientras sea necesaria para la cuenta, el contrato, la finalidad informada, la seguridad o una obligación aplicable. Las cuentas se mantienen mientras estén activas; al terminar se bloquean y se someten al procedimiento de eliminación, salvo información que deba conservarse justificadamente.',
      'Los documentos y registros financieros siguen las instrucciones de la organización, el periodo contable relacionado y el calendario acordado. Los registros de seguridad, facturación, autorizaciones y decisiones pueden conservarse durante el plazo necesario para auditoría, defensa de reclamaciones y obligaciones legales. Los respaldos se eliminan por rotación y una solicitud válida se reaplica mediante marcadores de eliminación antes de restaurar el servicio.',
      'Los plazos específicos aplicables a datos empresariales se documentan en el contrato o calendario de retención correspondiente. Fincilia no conserva información indefinidamente por conveniencia y no declara una eliminación completa mientras existan copias activas no justificadas.',
    ],
  },
  {
    title: 'Tus derechos y cómo ejercerlos',
    paragraphs: [
      'Puedes solicitar acceso, actualización, rectificación, prueba de autorización, información sobre el uso, revocación o eliminación escribiendo desde el correo asociado a privacy@fincilia.com. Indica el derecho que deseas ejercer y una descripción suficiente; no envíes contraseñas ni documentos financieros por correo. Verificaremos identidad y autoridad antes de responder.',
      'Para solicitudes sujetas a la legislación colombiana, las consultas se responden dentro de diez días hábiles, prorrogables por cinco días hábiles con aviso; los reclamos se atienden dentro de quince días hábiles, prorrogables por ocho días hábiles con aviso. Aplicaremos cualquier plazo más corto que resulte obligatorio en otra jurisdicción.',
      'Si Parallext LLC actúa como encargado de una organización, coordinaremos la solicitud con esa organización responsable. Los titulares en Colombia pueden acudir a la Superintendencia de Industria y Comercio después de agotar el trámite aplicable ante el responsable o encargado.',
    ],
  },
  {
    title: 'Seguridad, menores y cambios',
    paragraphs: [
      'Aplicamos controles técnicos y organizacionales orientados a aislamiento por empresa, acceso mínimo, cifrado, auditoría, respaldo y respuesta a incidentes. Ningún sistema elimina todo riesgo; reporta un incidente o vulnerabilidad a security@fincilia.com.',
      'Fincilia es un servicio empresarial y no está dirigido a menores de 18 años. Si detectamos una cuenta creada por un menor sin autoridad válida, la suspenderemos y coordinaremos su eliminación.',
      'Publicaremos una nueva versión cuando cambien materialmente las finalidades, categorías, proveedores o derechos. Si el cambio requiere nueva autorización, la solicitaremos antes de aplicarlo. Esta versión rige desde la fecha indicada al inicio del documento.',
    ],
  },
];

export const TERMS_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Partes, aceptación y elegibilidad',
    paragraphs: [
      `Estos términos regulan el uso de Fincilia, un producto operado por ${CONTROLLER}, con domicilio de contacto en ${ADDRESS}. Al crear una cuenta o usar el servicio aceptas esta versión de los términos y la política de privacidad.`,
      'Debes tener al menos 18 años y capacidad para obligarte. Si actúas por una empresa, firma contable u otra organización, declaras que tienes autoridad para aceptar estos términos en su nombre. Si existe una orden de servicio o contrato firmado, ese documento prevalece sobre estos términos en caso de conflicto.',
    ],
  },
  {
    title: 'Servicio y entorno UAT',
    paragraphs: [
      'Fincilia ayuda a cargar, estructurar, limpiar, comparar y revisar información financiera con trazabilidad. Sus resultados son herramientas de apoyo y requieren validación humana; no constituyen auditoría, certificación, asesoría legal, tributaria o financiera.',
      'El entorno UAT puede reiniciarse, cambiar o suspenderse para pruebas y correcciones. Mientras Fincilia muestre que el uso está limitado a datos sintéticos, no puedes cargar datos personales, financieros, bancarios, tributarios o confidenciales reales. La habilitación de datos reales se comunicará expresamente para un entorno autorizado y sujeto a los acuerdos correspondientes.',
    ],
  },
  {
    title: 'Cuenta, organizaciones y roles',
    bullets: [
      'Debes proporcionar información exacta, proteger tu acceso y avisar de inmediato a security@fincilia.com sobre actividad no reconocida.',
      'Google puede verificar tu identidad, pero Fincilia determina organizaciones, empresas, roles y permisos en sus propios servidores.',
      'Quien administra una organización es responsable de asignar y revocar accesos, verificar la autoridad de sus usuarios y mantener segregación de funciones adecuada.',
      'No puedes compartir sesiones, suplantar personas ni intentar obtener acceso a empresas o datos que no te correspondan.',
    ],
  },
  {
    title: 'Contenido y responsabilidades del cliente',
    paragraphs: [
      'Conservas los derechos sobre el contenido que cargas. Otorgas a Parallext LLC una autorización limitada para alojarlo, reproducirlo, transformarlo y transmitirlo únicamente en la medida necesaria para prestar, proteger y soportar Fincilia conforme a tus instrucciones y a la política de privacidad.',
      'Eres responsable de tener derechos, permisos y autorizaciones suficientes sobre el contenido; de revisar configuraciones, mapeos, conciliaciones y cierres; y de conservar los originales que exijan tus obligaciones. Fincilia no sustituye tus controles internos ni la responsabilidad profesional del contador, administrador o auditor.',
    ],
  },
  {
    title: 'Uso aceptable',
    bullets: [
      'No uses Fincilia para fraude, actividades ilícitas, malware, acoso, infracción de derechos o tratamiento no autorizado de datos.',
      'No eludas controles de acceso, aislamiento, límites, auditoría o seguridad, ni realices pruebas de carga o vulnerabilidad sin autorización escrita.',
      'No copies, revendas, sublicencies, hagas ingeniería inversa prohibida por ley ni presentes Fincilia como un servicio propio.',
      'No cargues secretos, credenciales bancarias, contraseñas, números completos de tarjeta o códigos de seguridad.',
      'Reporta vulnerabilidades de forma privada y no publiques información que facilite su explotación antes de coordinar una corrección.',
    ],
  },
  {
    title: 'Propiedad intelectual y comentarios',
    paragraphs: [
      'Fincilia, su software, diseño, documentación, marcas y componentes pertenecen a Parallext LLC o a sus licenciantes. Estos términos no transfieren propiedad sobre el servicio ni sobre el contenido de otros clientes.',
      'Puedes enviar sugerencias voluntarias. Parallext LLC puede utilizarlas para mejorar el producto sin obligación de pago, procurando no identificarte públicamente ni divulgar información confidencial.',
    ],
  },
  {
    title: 'Planes, pagos y cambios',
    paragraphs: [
      'El UAT es gratuito salvo acuerdo escrito distinto. Cuando se habiliten planes de pago, precio, impuestos, renovación, límites y cancelación se mostrarán antes de contratar o constarán en una orden de servicio. No realizaremos cargos basados únicamente en esta versión UAT.',
      'Podemos modificar funciones para mejorar seguridad, cumplimiento o utilidad. Avisaremos cambios materiales de estos términos por la aplicación o al correo de cuenta y solicitaremos una nueva aceptación cuando corresponda.',
    ],
  },
  {
    title: 'Suspensión, terminación y datos',
    paragraphs: [
      'Podemos limitar o suspender acceso ante riesgo de seguridad, uso ilegal, incumplimiento material o necesidad operativa urgente. Cuando sea razonable, daremos oportunidad de corregir antes de terminar la cuenta.',
      'Puedes dejar de usar el servicio y solicitar eliminación según /eliminar-cuenta. Antes de una terminación ordinaria podrás solicitar exportación cuando esa función esté disponible y tengas autorización. La terminación no elimina obligaciones que por su naturaleza deban sobrevivir, como confidencialidad, propiedad, pagos pendientes y conservación legal justificada.',
    ],
  },
  {
    title: 'Garantías y limitación de responsabilidad',
    paragraphs: [
      'Durante UAT, Fincilia se ofrece para evaluación y puede contener errores o interrupciones. En la máxima medida permitida por la ley, se presta sin garantías implícitas de disponibilidad continua, adecuación para una finalidad particular o ausencia total de errores.',
      'En la máxima medida permitida por la ley, Parallext LLC no responde por daños indirectos, pérdida de beneficios o decisiones contables tomadas sin revisión humana. La responsabilidad total derivada del servicio no excederá el mayor valor entre los importes pagados por el cliente durante los doce meses anteriores al hecho y USD 100. Esta limitación no aplica a fraude, dolo, culpa grave ni derechos que legalmente no puedan limitarse.',
    ],
  },
  {
    title: 'Ley, controversias y contacto',
    paragraphs: [
      'Estos términos se interpretan conforme a las leyes del Estado de Florida, Estados Unidos, sin desconocer normas imperativas de protección de datos o consumidores que resulten aplicables. Las controversias que no puedan resolverse directamente se someterán a los tribunales competentes del Condado de Orange, Florida, salvo que una norma imperativa permita otra jurisdicción.',
      `Las notificaciones a Parallext LLC pueden enviarse a legal@fincilia.com o a ${ADDRESS}. Para soporte escribe a support@fincilia.com. Teléfono de contacto: ${PHONE}.`,
    ],
  },
];

export const COOKIE_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Cookies estrictamente necesarias',
    bullets: [
      'fincilia_session: cookie httpOnly que mantiene la sesión autenticada hasta la expiración del token.',
      'fincilia_session_name: nombre visible utilizado por la interfaz durante la misma sesión; no contiene permisos ni decide acceso.',
      'fincilia_oidc_tx: cookie httpOnly cifrada que conserva state, nonce y el verificador PKCE durante un máximo de diez minutos mientras termina el ingreso con Google.',
      'Cookies de Amazon Cognito o Google: pueden aparecer en sus propios dominios durante la autenticación y se rigen por las políticas de esos proveedores.',
    ],
  },
  {
    title: 'Finalidad, control y duración',
    paragraphs: [
      'Estas cookies son necesarias para autenticar, prevenir falsificación de solicitudes, conservar la sesión y cerrar el flujo de forma segura. No usamos cookies publicitarias, analítica de terceros ni seguimiento entre sitios.',
      'Puedes eliminarlas desde el navegador; hacerlo cerrará la sesión o interrumpirá un ingreso en curso. Las cookies de sesión vencen con el token, las transitorias OAuth vencen en diez minutos y todas las cookies propias se eliminan al cerrar sesión.',
    ],
  },
  {
    title: 'Cambios futuros',
    paragraphs: [
      'Si añadimos analítica o cookies opcionales, actualizaremos este aviso con proveedor, finalidad y duración y solicitaremos consentimiento antes de activarlas cuando corresponda. Puedes consultar dudas en privacy@fincilia.com.',
    ],
  },
];

export const SECURITY_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Controles del servicio',
    bullets: [
      'Aislamiento por empresa mediante autorización en servidor y políticas RLS forzadas en PostgreSQL.',
      'Cifrado en tránsito, secretos fuera del código, sesiones cortas y autenticación administrada mediante Google y Amazon Cognito cuando se habilita.',
      'Dinero representado con decimal exacto, auditoría append-only y linaje de hechos financieros.',
      'Imágenes fijadas por digest, migraciones separadas, privilegios mínimos y administración cloud sin acceso SSH público.',
      'Backups, marcadores de eliminación y comprobaciones de restauración diseñados para evitar que reaparezcan datos eliminados.',
    ],
  },
  {
    title: 'Responsabilidad compartida',
    paragraphs: [
      'Parallext LLC protege la infraestructura y el servicio; cada organización debe administrar correctamente sus usuarios, roles, dispositivos, exportaciones y contenido. Ningún control ofrece riesgo cero y las funciones UAT no constituyen una certificación de seguridad.',
      'No envíes secretos o documentos por correo. Usa únicamente los flujos de carga autorizados y confirma siempre el entorno y la empresa antes de operar.',
    ],
  },
  {
    title: 'Reporte responsable',
    paragraphs: [
      'Envía hallazgos de forma privada a security@fincilia.com con descripción, impacto y pasos mínimos de reproducción. No accedas a datos ajenos, no interrumpas el servicio y no publiques detalles explotables antes de coordinar la corrección. Confirmaremos recepción y mantendremos comunicación razonable sobre el avance.',
    ],
  },
];

export const DPA_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Cuándo aplica',
    paragraphs: [
      'Este documento describe el modelo de acuerdo de tratamiento de datos de Parallext LLC para organizaciones que usan Fincilia con datos propios. No queda firmado por aceptar los términos web. El DPA aplicable debe identificar a las partes, el servicio contratado y la fecha de vigencia.',
    ],
  },
  {
    title: 'Contenido del acuerdo',
    bullets: [
      'Objeto, duración, naturaleza, finalidades, instrucciones y categorías de datos y titulares.',
      'Roles de responsable y encargado, deber de confidencialidad y medidas técnicas y organizacionales.',
      'Subencargados, ubicaciones, transmisión o transferencia internacional y mecanismo de objeción.',
      'Asistencia con derechos, incidentes, evaluaciones, auditorías y solicitudes de autoridades.',
      'Retorno, exportación, eliminación, legal hold, backups, evidencia y terminación.',
      'Anexos de seguridad, región, contactos, niveles de servicio y calendario de retención.',
    ],
  },
  {
    title: 'Cómo solicitarlo',
    paragraphs: [
      'Escribe a legal@fincilia.com indicando organización, país, tipo de datos y caso de uso. No adjuntes documentos reales. Parallext LLC responderá con el modelo y los anexos aplicables antes de habilitar el tratamiento solicitado.',
    ],
  },
];

export const SUBPROCESSOR_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Proveedores actuales o previstos',
    bullets: [
      'Amazon Web Services, Inc.: cómputo, red, almacenamiento, base de datos, secretos, registros técnicos e identidad administrada. Región principal prevista: sa-east-1, São Paulo, Brasil.',
      'Google LLC: proveedor opcional de identidad para openid, email y profile. No recibe documentos financieros de Fincilia ni acceso a Gmail, Drive, contactos o calendario.',
      'Namecheap, Inc. / Private Email: recepción y envío de comunicaciones dirigidas a los buzones @fincilia.com.',
      'Cloudflare, Inc.: DNS autoritativo, gestión del dominio y, si se habilita expresamente, controles de red y seguridad del borde.',
    ],
  },
  {
    title: 'Acceso y límites',
    paragraphs: [
      'Los proveedores reciben únicamente la información necesaria para su función y quedan sujetos a condiciones contractuales y controles de acceso. Parallext LLC no autoriza a un proveedor para vender datos, crear publicidad comportamental o entrenar modelos con documentos del cliente.',
      'Las ubicaciones exactas pueden variar por soporte, resiliencia o servicios globales del proveedor. Las organizaciones que requieran residencia o restricciones específicas deben acordarlas por escrito antes de cargar datos.',
    ],
  },
  {
    title: 'Cambios y objeciones',
    paragraphs: [
      'Publicaremos cambios materiales antes de que un nuevo proveedor trate datos empresariales. Los clientes con un DPA recibirán el aviso y plazo de objeción definido en ese acuerdo. Las consultas pueden enviarse a privacy@fincilia.com.',
    ],
  },
];

export const DELETION_SECTIONS: readonly LegalSection[] = [
  {
    title: 'Solicitar eliminación',
    paragraphs: [
      'Escribe desde el correo asociado a privacy@fincilia.com con el asunto “Eliminar cuenta Fincilia”, indicando si solicitas eliminar tu perfil, una organización que administras o información específica. No incluyas contraseñas, documentos o información financiera. Podemos pedir verificación adicional para impedir una eliminación no autorizada.',
      'Confirmaremos la recepción y clasificaremos la solicitud como consulta o reclamo conforme a la ley aplicable. Para Colombia aplican los tiempos descritos en la política de privacidad: diez días hábiles para consultas y quince días hábiles para reclamos, con las prórrogas informadas permitidas.',
    ],
  },
  {
    title: 'Alcance y ejecución',
    bullets: [
      'Bloqueamos el acceso y verificamos autoridad, membresías, objetos, exportaciones, trabajos y eventos relacionados.',
      'Evaluamos obligaciones contractuales o legales; cualquier retención se limita, documenta y comunica cuando sea posible.',
      'Registramos un marcador antes de purgar copias activas y derivadas y lo reaplicamos al restaurar backups.',
      'Informamos qué se eliminó, qué permanece temporalmente y la fecha o condición estimada para completar la reconciliación.',
      'La eliminación de un usuario no borra automáticamente registros que pertenecen a una organización y que esta deba conservar; en ese caso se revoca el acceso y se minimiza la identidad según corresponda.',
    ],
  },
  {
    title: 'Google y terceros',
    paragraphs: [
      'Eliminar Fincilia no elimina tu cuenta Google. También puedes retirar el acceso de Fincilia desde la configuración de tu cuenta Google. Fincilia dejará de usar el vínculo y conservará únicamente la evidencia mínima que resulte necesaria por seguridad o ley.',
      'Para mensajes ya enviados a nuestros buzones o datos administrados por tu organización, coordinaremos la solicitud con el proveedor o responsable correspondiente.',
    ],
  },
];
