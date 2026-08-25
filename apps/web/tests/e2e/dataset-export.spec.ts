import { expect, test } from '@playwright/test';

import {
  findPublishedDataset,
  publishedDatasetUrl,
  signInReviewer,
} from './reconciliation-helpers';

test('FNC-EXP-001 descarga el CSV canonico exacto sin certificar saldos', async ({
  page,
  request,
}) => {
  const dataset = await findPublishedDataset(request);
  await signInReviewer(page);
  await page.goto(publishedDatasetUrl(dataset));

  await expect(page.getByRole('heading', { name: 'Salida limpia' })).toBeVisible();
  await expect(page.getByText(/exportacion operativa no certificada/i)).toBeVisible();
  await expect(page.getByText(/no demuestra conciliacion de saldos/i)).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Descargar CSV canonico' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(
    /^fincilia-canonico-[0-9a-f-]{12}\.csv$/,
  );

  const source = await download.createReadStream();
  expect(source).not.toBeNull();
  const chunks: Buffer[] = [];
  if (source !== null) {
    for await (const chunk of source) {
      chunks.push(Buffer.from(chunk));
    }
  }
  const bytes = Buffer.concat(chunks);
  expect(Array.from(bytes.subarray(0, 3))).toEqual([0xef, 0xbb, 0xbf]);
  const text = bytes.subarray(3).toString('utf8');
  const lines = text.trimEnd().split('\r\n');
  expect(lines[0]).toBe(
    'record_ordinal,movement_id,occurred_on,posted_on,value_date,' +
      'accounting_date,amount,currency,direction,kind,description,reference,' +
      'state,canonical_schema_version,engine_release,lineage_state',
  );
  expect(lines).toHaveLength(dataset.rows + 1);
  expect(text).toMatch(/,\d+\.\d{12},[A-Z]{3},(inflow|outflow),/);
});
