import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { PrismaModule } from 'prisma/prisma.module';
import { UsersModule } from './users/users.module';
import { AuthModule } from './auth/auth.module';
import { AuthController } from './auth/auth.controller';
import { HealthController } from './health.controller';

@Module({
  imports: [PrismaModule, UsersModule, AuthModule],
  controllers: [AppController, AuthController, HealthController],
  providers: [AppService],
})
export class AppModule {}
