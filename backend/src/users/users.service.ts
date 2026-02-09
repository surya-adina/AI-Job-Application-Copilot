import { Injectable } from "@nestjs/common";
import { PrismaService } from "prisma/prisma.service";

@Injectable()
export class UsersService{
    constructor(private prisma: PrismaService) {}

    async create(email: string, passwordHash: string) {
        return this.prisma.user.create({
            data:{ email,passwordHash}
        })
    }
    async findAll() {
        return this.prisma.user.findMany()
    }
}