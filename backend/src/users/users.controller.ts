import { Body, Controller, Get, Post } from "@nestjs/common"
import { UsersService } from "./users.service"

@Controller('test-users')
export class UsersController{
    constructor(private usersService: UsersService) {}

    @Post('create')
    // test-only, hashed PW in production
    async create(@Body() body: { email: string, password: string}){
        return this.usersService.create(body.email, body.password);
    }

    @Get()
    async list(){
        return this.usersService.findAll()
        
    }
}