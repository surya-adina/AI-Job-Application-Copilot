import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { PrismaModule } from 'prisma/prisma.module';
import { UsersModule } from './users/users.module';
import { AuthModule } from './auth/auth.module';
import { AuthController } from './auth/auth.controller';
import { HealthController } from './health.controller';
import { ResumesModule } from './resumes/resumes.module';
import { JobsModule } from './jobs/jobs.module';

@Module({
  imports: [PrismaModule, UsersModule, AuthModule, ResumesModule, JobsModule],
  controllers: [AppController, AuthController, HealthController],
  providers: [AppService],
})
export class AppModule {}
