import {
  BadRequestException,
  Body,
  Controller,
  Headers,
  Param,
  ParseUUIDPipe,
  Post,
} from '@nestjs/common';
import { CreatedProbe, RecordsService } from './records.service';

interface CreateRecordBody {
  label?: unknown;
}

@Controller('companies/:companyId/records')
export class RecordsController {
  constructor(private readonly records: RecordsService) {}

  @Post()
  async create(
    @Param('companyId', new ParseUUIDPipe({ version: '4' })) companyId: string,
    @Headers('x-subject-id') subjectId: string | undefined,
    @Body() body: CreateRecordBody,
  ): Promise<CreatedProbe> {
    if (!subjectId || !/^[0-9a-f-]{36}$/i.test(subjectId)) {
      throw new BadRequestException('x-subject-id must be a synthetic UUID');
    }
    if (typeof body.label !== 'string' || body.label.trim().length === 0) {
      throw new BadRequestException('label is required');
    }
    if (body.label.length > 120) {
      throw new BadRequestException('label must be at most 120 characters');
    }
    return this.records.createSyntheticRecord(subjectId, companyId, body.label.trim());
  }
}
