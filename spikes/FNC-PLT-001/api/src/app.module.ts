import { Module } from '@nestjs/common';
import { DbService } from './db.service';
import { RecordsController } from './records.controller';
import { RecordsService } from './records.service';

@Module({
  controllers: [RecordsController],
  providers: [DbService, RecordsService],
})
export class AppModule {}
