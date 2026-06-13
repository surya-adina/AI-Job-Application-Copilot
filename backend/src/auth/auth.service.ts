import { ConflictException ,Injectable, UnauthorizedException } from "@nestjs/common";
import * as bcrypt from 'bcryptjs';
import { PrismaService } from "../../prisma/prisma.service";
import { JwtService } from "@nestjs/jwt";

@Injectable()
export class AuthService {
    constructor(
        private prisma: PrismaService,
        private jwt: JwtService,
    ) {}
    async register(email: string, password: string) {
        const existing = await this.prisma.user.findUnique({ where: { email } });
        if(existing) {
            throw new ConflictException('Email already registered');
        }
        const passwordHash = await bcrypt.hash(password, 12);

        const user = await this.prisma.user.create({
            data: { email, passwordHash },
            select: { id: true, email: true, createdAt: true},
        });
        return user;
    }
    async login(email: string, password: string) {
        const user = await this.prisma.user.findUnique({ where: { email }});
        if(!user) {
            throw new UnauthorizedException('Invalid Credentials');
        }
        const ok = await bcrypt.compare(password, user.passwordHash);
        if(!ok) {
            throw new UnauthorizedException('Incorrect Password');
        }
        const payload = { sub:user.id, email: user.email };
        const accessToken = await this.jwt.signAsync(payload);

        return { accessToken };
    }
}