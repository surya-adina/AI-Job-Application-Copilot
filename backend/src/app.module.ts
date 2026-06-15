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
import { ApplicationsModule } from './applications/applications.module';
import { AnalysesModule } from './analyses/analyses.module';
import { AiGatewayModule } from './ai-gateway/ai-gateway.module';

@Module({
  imports: [PrismaModule, UsersModule, AuthModule, ResumesModule, JobsModule, ApplicationsModule, AnalysesModule, AiGatewayModule],
  controllers: [AppController, AuthController, HealthController],
  providers: [AppService],
})
export class AppModule {}
