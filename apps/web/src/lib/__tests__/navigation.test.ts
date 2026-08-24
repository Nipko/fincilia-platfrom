import { describe, expect, it } from 'vitest';

import {
  MAX_NAVIGATION_PAGE,
  pageFromQuery,
  selectMappingVersion,
  singleQueryValue,
  withFlowContext,
} from '../navigation';

describe('withFlowContext', () => {
  it('conserva fuente, mapeo y pagina en una unica composicion', () => {
    expect(
      withFlowContext('/empresas/c-1/documentos/a-1/mapeo', {
        fuente: 'fuente con espacios',
        mapeo: 'mapping/2',
        pagina: 7,
        movimientosPagina: 3,
      }),
    ).toBe(
      '/empresas/c-1/documentos/a-1/mapeo?' +
        'fuente=fuente+con+espacios&mapeo=mapping%2F2&pagina=7&movimientosPagina=3',
    );
  });

  it('omite valores vacios y paginas que no son enteros seguros', () => {
    expect(
      withFlowContext('/ruta', {
        fuente: '  ',
        mapeo: null,
        pagina: -1,
      }),
    ).toBe('/ruta');
  });

  it('conserva version y ambas paginas en mapping -> perfil -> mapping', () => {
    const mappingUrl = withFlowContext('/empresas/c/documentos/a/mapeo', {
      documento: 'a',
      fuente: 's',
      mapeo: 'm',
      pagina: 4,
      movimientosPagina: 9,
    });
    const firstQuery = new URL(mappingUrl, 'https://fincilia.test').searchParams;
    const profileUrl = withFlowContext('/empresas/c/documentos/a', {
      documento: 'a',
      fuente: firstQuery.get('fuente'),
      mapeo: firstQuery.get('mapeo'),
      pagina: pageFromQuery(firstQuery.get('pagina') ?? undefined),
      movimientosPagina: pageFromQuery(
        firstQuery.get('movimientosPagina') ?? undefined,
      ),
    });
    const secondQuery = new URL(profileUrl, 'https://fincilia.test').searchParams;
    const returnUrl = withFlowContext('/empresas/c/documentos/a/mapeo', {
      documento: 'a',
      fuente: secondQuery.get('fuente'),
      mapeo: secondQuery.get('mapeo'),
      pagina: pageFromQuery(secondQuery.get('pagina') ?? undefined),
      movimientosPagina: pageFromQuery(
        secondQuery.get('movimientosPagina') ?? undefined,
      ),
    });

    expect(returnUrl).toBe(mappingUrl);
  });
});

describe('pageFromQuery', () => {
  it.each([
    [undefined, 0],
    ['', 0],
    ['-1', 0],
    ['1.5', 0],
    ['1e3', 0],
    ['no-es-numero', 0],
    ['9007199254740992', 0],
    ['0', 0],
    ['27', 27],
  ])('lee %s como %d', (raw, expected) => {
    expect(pageFromQuery(raw)).toBe(expected);
  });

  it('rechaza una query repetida en lugar de llamar trim sobre un array', () => {
    expect(pageFromQuery(['1', '2'])).toBe(0);
    expect(singleQueryValue(['fuente-a', 'fuente-b'])).toBeNull();
  });

  it('capa paginas antes de multiplicarlas por el tamano de pagina', () => {
    expect(pageFromQuery(String(MAX_NAVIGATION_PAGE))).toBe(MAX_NAVIGATION_PAGE);
    expect(pageFromQuery(String(MAX_NAVIGATION_PAGE + 1))).toBe(0);
    expect(
      pageFromQuery(String(Math.floor(Number.MAX_SAFE_INTEGER / 25) + 1)),
    ).toBe(0);
    expect(pageFromQuery(String(Number.MAX_SAFE_INTEGER))).toBe(0);
    expect(pageFromQuery(['1', String(MAX_NAVIGATION_PAGE)])).toBe(0);
  });
});

describe('selectMappingVersion', () => {
  it('no sustituye una fuente explicita por el primer mapeo historico', () => {
    expect(selectMappingVersion(null, true, ['mapping-fuente-anterior'])).toEqual({
      selectedId: null,
      invalidRequestedId: false,
    });
  });

  it('acepta solo una version solicitada que aparezca en la lista autorizada', () => {
    expect(selectMappingVersion('m-2', false, ['m-1', 'm-2'])).toEqual({
      selectedId: 'm-2',
      invalidRequestedId: false,
    });
    expect(selectMappingVersion('ajena', false, ['m-1'])).toEqual({
      selectedId: null,
      invalidRequestedId: true,
    });
  });
});
