import { Module } from '@nestjs/common'
import { AuthService} from './auth.service'
import { AuthController} from './auth.controller'
import { JwtModule } from '@nestjs/jwt'
import type ms from 'ms'

@Module({
    imports: [
        JwtModule.register({
            secret: process.env.JWT_SECRET!,
            signOptions: { expiresIn: process.env.JWT_EXPIRES_IN as ms.StringValue || '7d' },
    })],
    controllers: [AuthController],
    providers: [AuthService],
})

export class AuthModule {}